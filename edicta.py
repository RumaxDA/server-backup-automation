import os
import re
import time
import paramiko
from dotenv import load_dotenv
import uuid
from datetime import date, timedelta

load_dotenv()

yesterday_str = (date.today() - timedelta(days=1)).strftime("%y_%m_%d")

EDICTA_IP = os.getenv("EDICTA_IP")
EDICTA_USER = os.getenv("EDICTA_USERNAME")     
EDICTA_PASSWORD = os.getenv("EDICTA_PASSWORD")
NAS_PASSWORD = os.getenv("NAS_PASSWORD")       

# Polecenie
# backup_commands_edicta = [
#     f"scp -P 22 /srv/backup/db/Edicta-SOD_{yesterday_str}*.sql.zip admin@192.168.4.108:/share/CACHEDEV1_DATA/Backup/192.168.4.246_edicta/ ",
#     f"scp -P 22 /srv/backup/repo/Edicta-SOD_repository{yesterday_str}*.zip admin@192.168.4.108:/share/CACHEDEV1_DATA/Backup/192.168.4.246_edicta/"
# ]

backup_commands_edicta = [
    "id -u",
    "whoami",
]

# Testowe 
# backup_commands_edicta = [
#     "scp -P 22 /tmp/edicta_scp_test.txt "
#     "admin@192.168.4.108:/share/CACHEDEV1_DATA/Backup/"
#     "192.168.4.246_edicta/test/"
# ]

def run_command_on_edicta(shell, command, nas_password, timeout=3600):
    """Uruchamia komendę jako root, obsługuje hasło NAS-a
    i zwraca kod zakończenia komendy.
    """

    marker = f"EDICTA_DONE_{uuid.uuid4().hex}"

    # Podpowłoka zabezpiecza główną sesję przed np. poleceniem exit 7.
    full_command = (
        f"( {command} ); rc=$?; "
        f"printf '\\n{marker}:%s\\n' \"$rc\"\n"
    )

    shell.send(full_command)

    output_buffer = ""
    password_sent = False
    deadline = time.monotonic() + timeout

    password_prompt = "admin@192.168.4.108's password:".lower()
    marker_pattern = re.compile(re.escape(marker) + r":(\d+)")

    while time.monotonic() < deadline:
        if not shell.recv_ready():
            time.sleep(0.1)
            continue

        chunk = shell.recv(4096).decode("utf-8", errors="replace")

        # Usuwamy część sekwencji sterujących terminala.
        chunk = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', chunk)
        chunk = re.sub(r'\x1b\].*?\x07', '', chunk)

        print(chunk, end="", flush=True)

        output_buffer = (output_buffer + chunk)[-8192:]
        lower = output_buffer.lower()

        # Nie akceptujemy automatycznie nieznanego klucza hosta NAS-a.
        if "are you sure you want to continue connecting" in lower:
            raise RuntimeError(
                "NAS wymaga weryfikacji klucza SSH. "
                "Zweryfikuj fingerprint przed połączeniem."
            )

        # Obsługa prośby o hasło.
        if password_prompt in lower:
            if password_sent:
                raise RuntimeError(
                    "NAS ponownie prosi o hasło. "
                    "Sprawdź poprawność poświadczeń."
                )

            if not nas_password:
                raise RuntimeError("Nie ustawiono NAS_PASSWORD.")

            shell.send(nas_password + "\n")
            password_sent = True
            output_buffer = ""
            continue

        # Odbiór kodu zakończenia.
        match = marker_pattern.search(output_buffer)

        if match:
            return int(match.group(1))

    raise TimeoutError(
        f"Przekroczono limit czasu dla polecenia: {command}"
    )


def main():
    if not all([
        EDICTA_IP,
        EDICTA_USER,
        EDICTA_PASSWORD,
        NAS_PASSWORD,
    ]):
        print("[!] Brakuje wymaganych zmiennych w pliku .env.")
        return 1

    failed = False

    print(f"[*] Łączenie z Edicta ({EDICTA_IP})...")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            EDICTA_IP,
            username=EDICTA_USER,
            password=EDICTA_PASSWORD,
            timeout=10,
        )

        print(f"[+] Zalogowano pomyślnie do {EDICTA_IP}")

        shell = ssh.invoke_shell()
        time.sleep(1)

        if shell.recv_ready():
            shell.recv(4096)

        for cmd in backup_commands_edicta:
            print(f"\n[*] Uruchamianie polecenia: {cmd}")

            rc = run_command_on_edicta(shell, cmd, NAS_PASSWORD)

            if rc == 0:
                print(f"[+] Komenda zakończona sukcesem (kod {rc})")
            else:
                print(f"[!] Błąd! Komenda zwróciła kod {rc}")
                failed = True

        shell.close()

    except Exception as e:
        print(f"[!] Błąd połączenia lub wykonania: {e}")
        failed = True

    finally:
        ssh.close()
        print(f"[-] Rozłączono z {EDICTA_IP}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())