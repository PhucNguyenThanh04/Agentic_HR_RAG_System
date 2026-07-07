from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.core.configs.settings import settings
from src.utils.setup_logger import setup_logger
from src.core.db.base import Base
from src.core.db import model_registry  # noqa: F401

logger = setup_logger(__name__)

engine = create_async_engine(
    settings.database_url,      # postgresql+asyncpg://user:pass@localhost/dbname
    pool_size=5,
    max_overflow=10,
    echo=False,
    connect_args={
        "server_settings": {"TimeZone": settings.database_timezone}
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully.")


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
