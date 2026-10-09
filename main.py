
import puma
import edicta


def main():
    results = {}

    print("\n" + "=" * 50)
    print("ETAP 1/2: BACKUP PUMA")
    print("=" * 50)

    results["PUMA"] = puma.main()

    print("\n" + "=" * 50)
    print("ETAP 2/2: BACKUP EDICTA")
    print("=" * 50)

    results["EDICTA"] = edicta.main()

    print("\n" + "=" * 50)
    print("PODSUMOWANIE PIPELINE'U")
    print("=" * 50)

    for server, status in results.items():
        if status == 0:
            print(f"[+] {server}: SUKCES")
        else:
            print(f"[-] {server}: BŁĄD")

    all_success = all(status == 0 for status in results.values())

    if all_success:
        print("\n[+] Wszystkie backupy zakończone sukcesem.")
        return 0

    print("\n[!] Pipeline zakończył się z błędami.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())