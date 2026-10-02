# backend/models_db.py
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Text, Index
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), default="")
    role = Column(String(20), default="admin")  # admin, manager, viewer
    is_active = Column(Boolean, default=True)
    avatar_url = Column(String(500), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class LocalDemand(Base):
    __tablename__ = "local_demands"

    id = Column(String(100), primary_key=True, index=True)  # MoySklad UUID
    name = Column(String(100), index=True, nullable=False)
    moment = Column(String(50), index=True, nullable=False)
    sum = Column(Float, default=0.0)
    payed_sum = Column(Float, default=0.0)
    remaining = Column(Float, default=0.0)
    payment_status = Column(String(20), index=True, default="unpaid")
    payment_status_name = Column(String(50), default="")
    state_name = Column(String(50), index=True, default="")
    state_color = Column(String(20), default="#64748b")
    state_id = Column(String(100), default="")
    state_href = Column(String(255), default="")
    agent_name = Column(String(200), index=True, default="")
    agent_id = Column(String(100), index=True, default="")
    description = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_demand_agent_moment", "agent_id", "moment"),
        Index("ix_demand_state_moment", "state_name", "moment"),
    )


class LocalPayment(Base):
    __tablename__ = "local_payments"

    id = Column(String(100), primary_key=True, index=True)  # MoySklad UUID
    type = Column(String(20), nullable=False)  # "cash" | "card"
    name = Column(String(100), default="")
    sum = Column(Float, default=0.0)  # UZS da ekvivalent yoki UZS summasi
    moment = Column(String(50), index=True, default="")
    demand_id = Column(String(100), index=True, default="")
    agent_id = Column(String(100), index=True, default="")
    purpose = Column(Text, default="")
    is_usd = Column(Boolean, default=False)
    usd_amount = Column(Float, default=0.0)
    usd_rate = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_payment_agent_moment", "agent_id", "moment"),
    )


class LocalCounterparty(Base):
    __tablename__ = "local_counterparties"

    id = Column(String(100), primary_key=True, index=True)  # MoySklad UUID
    name = Column(String(200), index=True, nullable=False)
    phone = Column(String(50), default="")
    balance = Column(Float, default=0.0)
    group = Column(String(100), default="")
    status = Column(String(100), default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



class SyncLog(Base):
    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(50), index=True, nullable=False)
    records_synced = Column(Integer, default=0)
    status = Column(String(20), default="success")
    message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

class LocalAssortment(Base):
    __tablename__ = "local_assortments"

    id = Column(String(100), primary_key=True, index=True)
    name = Column(String(200), index=True, nullable=False)
    code = Column(String(100), index=True, default="")
    article = Column(String(100), index=True, default="")
    barcode = Column(String(100), index=True, default="")
    price = Column(Float, default=0.0)
    quantity = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SyncQueue(Base):
    __tablename__ = "sync_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action = Column(String(50), nullable=False)
    local_id = Column(String(100), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    status = Column(String(20), default="pending", index=True)
    error_message = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class LocalDemandPosition(Base):
    __tablename__ = "local_demand_positions"

    id = Column(String(100), primary_key=True, index=True)
    demand_id = Column(String(100), index=True, nullable=False)
    demand_name = Column(String(100), index=True, default="")
    agent_id = Column(String(100), index=True, default="")
    agent_name = Column(String(200), index=True, default="")
    moment = Column(String(50), index=True, default="")
    state_name = Column(String(50), default="")
    state_color = Column(String(20), default="#64748b")
    demand_sum = Column(Float, default=0.0)
    demand_remaining = Column(Float, default=0.0)
    description = Column(Text, default="")

    assortment_id = Column(String(100), index=True, nullable=False)
    assortment_name = Column(String(255), index=True, default="")
    assortment_code = Column(String(100), index=True, default="")
    assortment_article = Column(String(100), index=True, default="")
    assortment_barcode = Column(String(100), index=True, default="")

    quantity = Column(Float, default=0.0)
    price = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_demand_pos_assortment", "assortment_id"),
        Index("ix_demand_pos_code", "assortment_code"),
        Index("ix_demand_pos_name", "assortment_name"),
        Index("ix_demand_pos_moment", "moment"),
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    key = Column(String(50), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


