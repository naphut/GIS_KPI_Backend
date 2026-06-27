from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app import models, schemas

# ==========================================
# Unit CRUD Operations
# ==========================================
async def get_units(db: AsyncSession, skip: int = 0, limit: int = 100):
    """
    Retrieve all units with pagination support.
    """
    result = await db.execute(select(models.Unit).offset(skip).limit(limit))
    return result.scalars().all()

async def get_unit_by_id(db: AsyncSession, unit_id: int):
    """
    Retrieve a single unit by its primary ID.
    """
    result = await db.execute(select(models.Unit).where(models.Unit.id == unit_id))
    return result.scalar_one_or_none()

async def get_unit_by_name(db: AsyncSession, name: str):
    """
    Retrieve a single unit by its unique name.
    """
    result = await db.execute(select(models.Unit).where(models.Unit.name == name))
    return result.scalar_one_or_none()

async def create_unit(db: AsyncSession, unit: schemas.UnitCreate):
    """
    Insert a new unit record into the database.
    """
    db_unit = models.Unit(name=unit.name, description=unit.description)
    db.add(db_unit)
    await db.commit()
    await db.refresh(db_unit)
    return db_unit

# ==========================================
# KPI CRUD Operations
# ==========================================
async def get_kpis(db: AsyncSession, skip: int = 0, limit: int = 100):
    """
    Retrieve all KPIs with pagination support.
    """
    result = await db.execute(
        select(models.KPI).options(selectinload(models.KPI.unit)).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def create_kpi(db: AsyncSession, kpi: schemas.KPICreate):
    """
    Insert a new KPI record into the database.
    """
    db_kpi = models.KPI(
        name=kpi.name,
        value=kpi.value,
        unit_id=kpi.unit_id
    )
    db.add(db_kpi)
    await db.commit()
    await db.refresh(db_kpi, attribute_names=["unit"])
    return db_kpi

# ==========================================
# Telegram Template CRUD Operations
# ==========================================
async def get_templates(db: AsyncSession, skip: int = 0, limit: int = 100):
    """
    Retrieve all telegram message templates.
    """
    result = await db.execute(
        select(models.TelegramTemplate).order_by(models.TelegramTemplate.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()

async def get_template_by_content(db: AsyncSession, content: str):
    """
    Retrieve a single template by its content.
    """
    result = await db.execute(select(models.TelegramTemplate).where(models.TelegramTemplate.content == content))
    return result.scalar_one_or_none()

async def create_template(db: AsyncSession, template: schemas.TelegramTemplateCreate):
    """
    Insert a new template record into the database.
    """
    db_template = models.TelegramTemplate(content=template.content)
    db.add(db_template)
    await db.commit()
    await db.refresh(db_template)
    return db_template

async def delete_template(db: AsyncSession, template_id: int):
    """
    Delete a template record from the database.
    """
    result = await db.execute(select(models.TelegramTemplate).where(models.TelegramTemplate.id == template_id))
    db_template = result.scalar_one_or_none()
    if db_template:
        await db.delete(db_template)
        await db.commit()
        return True
    return False

# ==========================================
# GIS Store (Key-Value) CRUD Operations
# ==========================================
async def get_store_value(db: AsyncSession, key: str):
    """
    Retrieve a key-value pair from the store.
    """
    result = await db.execute(select(models.GISStore).where(models.GISStore.key == key))
    return result.scalar_one_or_none()

async def upsert_store_value(db: AsyncSession, item: schemas.GISStoreCreate):
    """
    Create or update a key-value pair in the store.
    """
    result = await db.execute(select(models.GISStore).where(models.GISStore.key == item.key))
    db_item = result.scalar_one_or_none()
    
    if db_item:
        db_item.value = item.value
    else:
        db_item = models.GISStore(key=item.key, value=item.value)
        db.add(db_item)
        
    await db.commit()
    await db.refresh(db_item)
    return db_item

async def delete_store_value(db: AsyncSession, key: str):
    """
    Delete a key-value pair from the store.
    """
    result = await db.execute(select(models.GISStore).where(models.GISStore.key == key))
    db_item = result.scalar_one_or_none()
    if db_item:
        await db.delete(db_item)
        await db.commit()
        return True
    return False
