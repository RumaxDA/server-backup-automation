from datetime import date
import os
import re
import shlex
import time
import uuid
from dotenv import load_dotenv
import paramiko

# Ładowanie zmiennych środowiskowych
load_dotenv()

today_str = date.today().strftime("%Y-%m-%d")

# Konfiguracja NAS-a (cel backupów)
NAS_PASSWORD = os.environ["NAS_PASSWORD"]

# Lista serwerów do przetworzenia
servers = [
    {
        "ip": os.environ["PUMA_IP"],
        "username": os.environ["PUMA_USERNAME"],
        "password": os.environ["PUMA_PASSWORD"],
    },
    # {
    #     'ip': os.environ['EDICTA_IP'],
    #     'username': os.environ['EDICTA_USERNAME'],
    #     'password': os.environ['EDICTA_PASSWORD']
    # }
]

# Komendy do wykonania na Pumie
# backup_commands_puma = [
#     f"scp -P 22 /srv/samba/backup/JST_PUMA_*{today_str}*.xz admin@192.168.4.108:/share/CACHEDEV1_DATA/Backup/192.168.4.50_puma/",
#     f"scp -P 22 /srv/samba/backup/PUMA_*{today_str}*.xz admin@192.168.4.108:/share/CACHEDEV1_DATA/Backup/192.168.4.50_puma/",
#     f"scp -P 22 /srv/samba/backup/LgcDoc/Backup.zpaq.daily admin@192.168.4.108:/share/CACHEDEV1_DATA/Backup/192.168.4.50_puma/Ldoc_S/",
#     f"scp -P 22 /srv/samba/backup/LgcDoc/Backup.zpaq.daily.sha384 admin@192.168.4.108:/share/CACHEDEV1_DATA/Backup/192.168.4.50_puma/Ldoc_S/",
#     f"scp -P 22 /srv/samba/backup/LgcDoc.podlegle/Backup.zpaq.daily admin@192.168.4.108:/share/CACHEDEV1_DATA/Backup/192.168.4.50_puma/Ldoc_J/",
#     f"scp -P 22 /srv/samba/backup/LgcDoc.podlegle/Backup.zpaq.daily.sha384 admin@192.168.4.108:/share/CACHEDEV1_DATA/Backup/192.168.4.50_puma/Ldoc_J/",
# ]

#Komendy testowe
backup_commands_puma = [    
    "id -u",
    "whoami",
    "exit 7",
]


def run_as_root_and_handle_nas(channel, command, timeout=3600):
    """
    Uruchamia polecenie jako root, obsługuje prompt o hasło NAS-a
    i zwraca kod zakończenia polecenia.
    """

    marker = f"__PYTHON_DONE_{uuid.uuid4().hex}__"

    # Najpierw kończy się su, a dopiero potem powłoka admina
    # wypisuje kod zakończenia i unikalny znacznik.
    remote_command = (
        f"export TERM=dumb; "
        f"su -l root -c {shlex.quote(command)}; "
        f"rc=$?; printf '\\n{marker}:%s\\n' \"$rc\"\n"
    )

    channel.send(remote_command)

    pending = ""
    password_sent = False
    deadline = time.monotonic() + timeout

    password_prompt = f"admin@192.168.4.108's password:".lower()
    marker_pattern = re.compile(re.escape(marker) + r":(\d+)")


    while time.monotonic() < deadline:

        if not channel.recv_ready():
            time.sleep(0.1)
            continue

        chunk = channel.recv(4096).decode(
            "utf-8", errors="replace"
        )

        print(chunk, end="", flush=True)

        pending = (pending + chunk)[-8192:]
        lower = pending.lower()

        # Nie akceptujemy automatycznie nieznanego klucza hosta.
        if "are you sure you want to continue connecting" in lower:
            raise RuntimeError(
                "NAS wymaga weryfikacji klucza SSH. "
                "Zweryfikuj fingerprint przed połączeniem."
            )

        # Obsługa żądania hasła przez scp.
        if password_prompt in lower:

            if password_sent:
                raise RuntimeError(
                    "NAS ponownie prosi o hasło. "
                    "Sprawdź poprawność poświadczeń."
                )

            channel.send(NAS_PASSWORD + "\n")
            password_sent = True
            pending = ""
            continue

        # Zwracamy kod dopiero po odebraniu znacznika.
        match = marker_pattern.search(pending)

        if match:
            return int(match.group(1))

    raise TimeoutError(
        f"Przekroczono limit czasu dla polecenia: {command}"
    )

def main():
    failed = False

    for server in servers:
        print(f"[*] Łączenie z serwerem {server['ip']}...")

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(
                hostname=server["ip"],
                username=server["username"],
                password=server["password"],
                timeout=10,
            )
            print(f"[*] Zalogowano pomyślnie do {server['ip']}")

            channel = ssh.invoke_shell()
            time.sleep(1)

            if channel.recv_ready():
                channel.recv(65535)

            if server["ip"] == os.environ["PUMA_IP"]:
                for command in backup_commands_puma:
                    print(f"\n[*] Uruchamianie polecenia: {command}")

                    exit_status = run_as_root_and_handle_nas(
                        channel, command
                    )

                    if exit_status == 0:
                        print("[+] Komenda zakończona sukcesem (kod 0)")
                    else:
                        print(
                            f"[-] Komenda zwróciła błąd "
                            f"(kod wyjścia: {exit_status})"
                        )
                        failed = True

        except Exception as e:
            print(
                f"\n[KRYTYCZNY] Nie udało się przetworzyć "
                f"serwera {server['ip']}: {e}"
            )
            failed = True

        finally:
            ssh.close()
            print(
                f"[-] Rozłączono z {server['ip']}\n"
                + "-" * 40
            )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())