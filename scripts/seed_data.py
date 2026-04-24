"""Seed Data Script.
================

Creates initial admin user and sample data for development.
"""

import asyncio
import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Database URL - matches config.py
DATABASE_URL = "postgresql+asyncpg://omics:omics_secret@localhost:5433/omics_db"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


async def seed_database():
    """Seed the database with initial data."""
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if admin user exists
        result = await session.execute(
            text("SELECT id FROM omics.users WHERE email = :email"), {"email": "admin@omics.local"}
        )
        existing = result.fetchone()

        if existing:
            print("Admin user already exists!")
            return

        # Create admin user
        admin_id = uuid.uuid4()
        hashed_password = hash_password("admin123")

        await session.execute(
            text("""
                INSERT INTO omics.users (id, email, hashed_password, full_name, is_active, is_superuser, created_at, updated_at)
                VALUES (:id, :email, :hashed_password, :full_name, :is_active, :is_superuser, :created_at, :updated_at)
            """),
            {
                "id": admin_id,
                "email": "admin@omics-suite.dev",
                "hashed_password": hashed_password,
                "full_name": "Admin User",
                "is_active": True,
                "is_superuser": True,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            },
        )

        await session.commit()

        print("=" * 50)
        print("Database seeded successfully!")
        print("=" * 50)
        print("\nAdmin User Created:")
        print("  Email:    admin@omics-suite.dev")
        print("  Password: admin123")
        print(f"  ID:       {admin_id}")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(seed_database())
