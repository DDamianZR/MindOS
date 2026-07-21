"""Genera el hash Argon2 de una contraseña para `MINDOS_ADMIN_PASSWORD_HASH` en `.env`
(F3-T1: el Gateway nunca guarda la contraseña en texto plano, solo su hash)."""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway.src.application.services.security import hash_password  # noqa: E402


def main():
    password = getpass.getpass("Contraseña del admin de MindOS: ")
    confirm = getpass.getpass("Confírmala: ")
    if password != confirm:
        print("\n[ERROR] Las contraseñas no coinciden.")
        sys.exit(1)

    print("\nAgrega esta línea a tu .env:\n")
    print(f"MINDOS_ADMIN_PASSWORD_HASH={hash_password(password)}")


if __name__ == "__main__":
    main()
