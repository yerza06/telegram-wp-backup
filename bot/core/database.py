from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


_engine = None
_session_maker = None


def get_engine(database_url: str):
    global _engine
    if _engine is None:
        _engine = create_async_engine(database_url, echo=False)
    return _engine


def get_session_maker(database_url: str) -> async_sessionmaker[AsyncSession]:
    global _session_maker
    if _session_maker is None:
        engine = get_engine(database_url)
        _session_maker = async_sessionmaker(engine, expire_on_commit=False)
    return _session_maker


async def get_session(database_url: str) -> AsyncSession:
    maker = get_session_maker(database_url)
    async with maker() as session:
        yield session
