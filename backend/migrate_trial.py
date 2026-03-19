"""
FiscalIA — Migration script
Gives all existing users 60 days of Premium from today.
Run once: python migrate_trial.py
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal, init_db
from app.models.user import User


async def migrate():
    await init_db()
    expires_at = datetime.utcnow() + timedelta(days=60)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        updated = 0
        for user in users:
            # Only update if they don't already have a longer premium period
            if user.plan_expires_at is None or user.plan_expires_at < expires_at:
                user.plan = "premium"
                user.plan_expires_at = expires_at
                updated += 1
        await db.commit()
        print(f"✅ {updated}/{len(users)} users updated to Premium (60 days until {expires_at.strftime('%d/%m/%Y')})")


if __name__ == "__main__":
    asyncio.run(migrate())
