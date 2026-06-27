from typing import Optional
from pydantic import BaseModel, ConfigDict
from datetime import datetime

# ==========================================
# Unit Schemas
# ==========================================
class UnitBase(BaseModel):
    name: str
    description: Optional[str] = None

class UnitCreate(UnitBase):
    pass

class Unit(UnitBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# KPI Schemas
# ==========================================
class KPIBase(BaseModel):
    name: str
    value: float
    unit_id: int

class KPICreate(KPIBase):
    pass

class KPI(KPIBase):
    id: int
    recorded_at: datetime
    unit: Optional[Unit] = None

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# Telegram Template Schemas
# ==========================================
class TelegramTemplateBase(BaseModel):
    content: str

class TelegramTemplateCreate(TelegramTemplateBase):
    pass

class TelegramTemplate(TelegramTemplateBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# GIS Store (Key-Value) Schemas
# ==========================================
class GISStoreBase(BaseModel):
    key: str
    value: str

class GISStoreCreate(GISStoreBase):
    pass

class GISStore(GISStoreBase):
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
