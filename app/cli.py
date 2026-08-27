"""CLI helpers — run with: python -m app.cli <command>"""

import asyncio
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.user import AppUser, UserRole
from app.services.auth import hash_password


async def _create_superadmin(username: str = "", email: str = "", password: str = "") -> None:
    print("Creating SUPER_ADMIN account")
    if not username:
        username = input("Username: ").strip()
    if not email:
        email = input("Email: ").strip()
    if not password:
        password = input("Password (min 8 chars): ").strip()

    if len(password) < 8:
        print("Password too short.")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(AppUser).where(AppUser.username == username))
        if existing.scalar_one_or_none():
            print(f"User '{username}' already exists.")
            sys.exit(1)

        user = AppUser(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.SUPER_ADMIN,
            jzd_id=None,
        )
        db.add(user)
        await db.commit()
        print(f"SUPER_ADMIN '{username}' created successfully.")


def main() -> None:
    commands = {"create-superadmin": _create_superadmin}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(f"Usage: python -m app.cli [{' | '.join(commands)}] [username email password]")
        sys.exit(1)
    asyncio.run(commands[sys.argv[1]](*sys.argv[2:]))


if __name__ == "__main__":
    main()
