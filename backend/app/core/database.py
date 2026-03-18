from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


def get_db_url() -> str:
    url = settings.DATABASE_URL
    # Convert postgres:// to postgresql+asyncpg:// (Supabase format)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(
    get_db_url(),
    echo=False,
    # PostgreSQL connection pool settings
    pool_pre_ping=True,       # Test connections before using them
    pool_recycle=300,         # Recycle connections every 5 minutes
    pool_size=5,
    max_overflow=10,
)

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
