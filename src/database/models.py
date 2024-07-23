from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import BigInteger, String, DateTime, ForeignKey, Boolean, Integer, Table, Column
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine

engine = create_async_engine(url='sqlite+aiosqlite:///db.sqlite3')

async_session = async_sessionmaker(engine)


class Base(AsyncAttrs, DeclarativeBase):
    pass


wishlist_fragrance = Table(
    'wishlist_fragrance', Base.metadata,
    Column('wishlist_id', Integer, ForeignKey('Wishlists.id'), primary_key=True),
    Column('fragrance_id', Integer, ForeignKey('Fragrances.id'), primary_key=True)
)


class Fragrance(Base):
    __tablename__ = "Fragrances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    is_sold_out: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str] = mapped_column(String(200))
    parsed_datetime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(ZoneInfo('Asia/Almaty')))
    wishlists = relationship('Wishlist', secondary=wishlist_fragrance, back_populates='fragrances', lazy="selectin")


class Wishlist(Base):
    __tablename__ = "Wishlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    receive_notification: Mapped[bool] = mapped_column(Boolean, default=True)
    fragrances = relationship('Fragrance', secondary=wishlist_fragrance, back_populates='wishlists', lazy="selectin")


async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
