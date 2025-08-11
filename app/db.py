import enum
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import (
    BigInteger, String, DateTime, Boolean, Float, Enum as SAEnum, func,
    select, delete, update, distinct, text
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import DATABASE_URL, USERS_PER_PAGE

# --- Database Setup ---
engine = create_async_engine(DATABASE_URL)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(AsyncAttrs, DeclarativeBase):
    pass

# --- ORM Models ---
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(32))
    first_name: Mapped[str] = mapped_column(String(128))
    subscription_tier: Mapped[str] = mapped_column(String(10), default='free')
    subscription_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime)
    join_date: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    credits: Mapped[int] = mapped_column(default=10)

class ScheduledTask(Base):
    __tablename__ = 'scheduled_tasks'
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[str] = mapped_column(String, unique=True)
    asset: Mapped[str] = mapped_column(String(20))
    hour: Mapped[int]
    minute: Mapped[int]
    timezone: Mapped[str] = mapped_column(String, default='Asia/Baghdad')

class AlertType(enum.Enum):
    ABOVE = "above"
    BELOW = "below"

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer

# ... (other imports)

class PriceAlert(Base):
    __tablename__ = 'price_alerts'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    asset: Mapped[str] = mapped_column(String(20))
    target_price: Mapped[float] = mapped_column(Float)
    alert_type: Mapped[AlertType] = mapped_column(SAEnum(AlertType))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    triggered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    is_one_time: Mapped[bool] = mapped_column(Boolean, default=True)


async def init_database():
    """Initializes the database and runs migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logging.info("Database initialized with SQLAlchemy.")
    # The migration logic from the original file was complex and specific to a one-time change.
    # For a clean project, it's better to handle migrations with a dedicated tool like Alembic.
    # The create_all command is sufficient for starting a new project.
    # If the 'is_one_time' column is missing, it will be created by the line above.

# --- Database Interaction Class ---
class DB:
    @staticmethod
    async def get_or_update_user(user_id: int, username: str, first_name: str) -> User:
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                user = User(id=user_id, username=username, first_name=first_name)
                session.add(user)
            else:
                user.username = username
                user.first_name = first_name
            await session.commit()
            await session.refresh(user)
            return user

    @staticmethod
    async def get_user(user_id: int) -> Optional[User]:
        async with async_session() as s:
            return await s.get(User, user_id)

    @staticmethod
    async def get_stats():
        async with async_session() as s:
            user_stats_query = select(
                func.count(User.id),
                func.count(User.id).filter(User.subscription_tier == 'free'),
                func.count(User.id).filter(User.subscription_tier == 'standard'),
                func.count(User.id).filter(User.subscription_tier == 'pro'),
                func.count(User.id).filter(User.is_vip == True)
            )
            user_res = await s.execute(user_stats_query)
            total, free, standard, pro, vips = user_res.one()

            task_stats_query = select(func.count(ScheduledTask.id))
            tasks = (await s.execute(task_stats_query)).scalar_one()

            alert_stats_query = select(func.count(PriceAlert.id))
            alerts = (await s.execute(alert_stats_query)).scalar_one()

            return {
                "total_users": total, "free_users": free, "standard_users": standard,
                "pro_users": pro, "vip_users": vips, "active_tasks": tasks, "total_alerts": alerts
            }

    @staticmethod
    async def change_credits(user_id: int, amount: int):
        async with async_session() as s:
            await s.execute(update(User).where(User.id == user_id).values(credits=User.credits + amount))
            await s.commit()

    @staticmethod
    async def update_user_tier(user_id: int, tier: str):
        expiry = (datetime.now() + timedelta(days=30)) if tier in ['standard', 'pro'] else None
        async with async_session() as s:
            await s.execute(update(User).where(User.id == user_id).values(subscription_tier=tier, subscription_expiry=expiry))
            await s.commit()

    @staticmethod
    async def set_vip_status(user_id: int, status: bool) -> bool:
        async with async_session() as s:
            res = await s.execute(update(User).where(User.id == user_id).values(is_vip=status))
            await s.commit()
            return res.rowcount > 0

    @staticmethod
    async def get_all_user_ids() -> List[int]:
        async with async_session() as s:
            return (await s.execute(select(User.id))).scalars().all()

    @staticmethod
    async def get_vip_users() -> List[User]:
        async with async_session() as s:
            return (await s.execute(select(User).where(User.is_vip == True))).scalars().all()

    @staticmethod
    async def get_all_active_users() -> List[User]:
        async with async_session() as s:
            return (await s.execute(select(User))).scalars().all()

    @staticmethod
    async def add_task(job_id: str, asset: str, hour: int, minute: int):
        async with async_session() as s:
            s.add(ScheduledTask(job_id=job_id, asset=asset, hour=hour, minute=minute))
            await s.commit()

    @staticmethod
    async def get_all_tasks() -> List[ScheduledTask]:
        async with async_session() as s:
            return (await s.execute(select(ScheduledTask))).scalars().all()

    @staticmethod
    async def delete_task(job_id: str):
        async with async_session() as s:
            await s.execute(delete(ScheduledTask).where(ScheduledTask.job_id == job_id))
            await s.commit()

    @staticmethod
    async def get_all_users(page: int = 1, per_page: int = USERS_PER_PAGE):
        async with async_session() as s:
            offset = (page - 1) * per_page
            query = select(User).order_by(User.join_date.desc()).offset(offset).limit(per_page)
            users = (await s.execute(query)).scalars().all()
            total_users_query = select(func.count(User.id))
            total = (await s.execute(total_users_query)).scalar_one()
            return users, total

    @staticmethod
    async def get_subscribers() -> List[User]:
        async with async_session() as s:
            query = select(User).where(User.subscription_tier.in_(['standard', 'pro'])).order_by(User.subscription_expiry.desc())
            return (await s.execute(query)).scalars().all()

    @staticmethod
    async def get_expired_users() -> List[User]:
        async with async_session() as s:
            query = select(User).where(User.subscription_expiry < datetime.now()).order_by(User.subscription_expiry.desc())
            return (await s.execute(query)).scalars().all()

    @staticmethod
    async def update_task(job_id: str, new_hour: int, new_minute: int):
        async with async_session() as s:
            await s.execute(update(ScheduledTask).where(ScheduledTask.job_id == job_id).values(hour=new_hour, minute=new_minute))
            await s.commit()

    # --- Price Alert DB Methods ---
    @staticmethod
    async def add_price_alert(user_id: int, asset: str, target_price: float, alert_type: AlertType, is_one_time: bool = True) -> PriceAlert:
        async with async_session() as s:
            alert = PriceAlert(user_id=user_id, asset=asset, target_price=target_price, alert_type=alert_type, is_one_time=is_one_time)
            s.add(alert)
            await s.commit()
            await s.refresh(alert)
            return alert

    @staticmethod
    async def get_user_price_alerts(user_id: int, active_only: bool = True) -> List[PriceAlert]:
        async with async_session() as s:
            query = select(PriceAlert).where(PriceAlert.user_id == user_id)
            if active_only:
                query = query.where(PriceAlert.is_active == True)
            query = query.order_by(PriceAlert.created_at.desc())
            return (await s.execute(query)).scalars().all()

    @staticmethod
    async def get_all_active_price_alerts() -> List[PriceAlert]:
        async with async_session() as s:
            return (await s.execute(select(PriceAlert).where(PriceAlert.is_active == True))).scalars().all()

    @staticmethod
    async def deactivate_price_alert(alert_id: int):
        async with async_session() as s:
            await s.execute(update(PriceAlert).where(PriceAlert.id == alert_id).values(is_active=False, triggered_at=func.now()))
            await s.commit()

    @staticmethod
    async def delete_price_alert(alert_id: int):
        async with async_session() as s:
            await s.execute(delete(PriceAlert).where(PriceAlert.id == alert_id))
            await s.commit()

    @staticmethod
    async def get_price_alert_by_id(alert_id: int) -> Optional[PriceAlert]:
        async with async_session() as s:
            return await s.get(PriceAlert, alert_id)
            
    @staticmethod
    async def get_distinct_alert_assets() -> List[str]:
        async with async_session() as s:
            return (await s.execute(
                select(distinct(PriceAlert.asset)).where(PriceAlert.is_active == True)
            )).scalars().all()

    @staticmethod
    async def search_user(query: str) -> Optional[User]:
        """Searches for a user by ID or username."""
        async with async_session() as s:
            # Try searching by ID first if the query is a digit
            if query.isdigit():
                user = await s.get(User, int(query))
                if user:
                    return user
            
            # If not found by ID or query is not a digit, search by username
            # The username in the DB might not have the '@' prefix
            search_username = query.lstrip('@')
            result = await s.execute(select(User).where(User.username.ilike(f"%{search_username}%")))
            return result.scalars().first()
