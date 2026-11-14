"""Provision mentor/lead accounts without public privilege escalation."""
import argparse
import getpass
import os

import psycopg
from psycopg.rows import dict_row

from server.portal_auth import create_account, valid_credentials


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=("intern", "mentor", "lead"), default="intern")
    parser.add_argument("--track", choices=("backend", "analytics", "marketing"), default="backend")
    args = parser.parse_args()
    password = getpass.getpass("Пароль (минимум 12 символов): ")
    if password != getpass.getpass("Повторите пароль: "):
        parser.error("Пароли не совпадают")
    email = args.email.strip().lower()
    if not valid_credentials(dict(email=email, password=password, name=args.name), True):
        parser.error("Проверьте email, имя и длину пароля (12–128 символов)")
    with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
        account = create_account(conn, email, password, args.name.strip(), args.role, args.track)
    print("Создан аккаунт:", account["email"], account["role"])


if __name__ == "__main__":
    main()
