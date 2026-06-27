from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from services.common.database import Base

class Unit(Base):
    """
    Represents a geographical or organizational unit.
    """
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    kpis: Mapped[list["KPI"]] = relationship("KPI", back_populates="unit", cascade="all, delete-orphan")

class KPI(Base):
    """
    Represents a Key Performance Indicator record.
    """
    __tablename__ = "kpis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit_id: Mapped[int] = mapped_column(Integer, ForeignKey("units.id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    unit: Mapped["Unit"] = relationship("Unit", back_populates="kpis")

class TelegramTemplate(Base):
    """
    Represents a reusable template comment for Telegram reports.
    """
    __tablename__ = "telegram_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    content: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class GISStore(Base):
    """
    Key-Value store to persist frontend dashboard data in compressed JSON format.
    Includes indices and versioning for high scalability and concurrent writes.
    """
    __tablename__ = "gis_store"

    key: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
    
    # Scalability optimizations:
    # 1. Index on updated_at for fast date filtering/sorting queries.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow, 
        index=True
    )
    
    # 2. Concurrency check version for optimistic locking.
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
