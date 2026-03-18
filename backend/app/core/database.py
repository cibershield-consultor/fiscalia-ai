import re
import ssl as ssl_module
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


def get_db_url() -> str:
    url = settings.DATABASE_URL

    # Strip ALL query parameters — asyncpg receives ssl via connect_args instead
    if "?" in url:
        url = url.split("?")[0]

    # Convert to asyncpg dialect
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return url


def is_postgres(url: str) -> bool:
    return "postgresql" in url or "postgres" in url


db_url = get_db_url()

if is_postgres(db_url):
    # Create SSL context for asyncpg
    ssl_ctx = ssl_module.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl_module.CERT_NONE

    engine = create_async_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=10,
        connect_args={"ssl": ssl_ctx},
    )
else:
    engine = create_async_engine(db_url, echo=False)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    from app.models import user, conversation, invoice, transaction  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
