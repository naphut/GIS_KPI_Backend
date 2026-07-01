import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
import json

from services.common.database import engine, Base, get_db
from services.common import models, schemas
from services.common.cache import cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("asset_service")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables and perform online schema migrations
    async with engine.begin() as conn:
        from sqlalchemy import text
        try:
            await conn.execute(text("ALTER TABLE gis_store ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'draft'"))
            await conn.execute(text("ALTER TABLE gis_store ADD COLUMN IF NOT EXISTS result VARCHAR NULL"))
        except Exception as e:
            logger.warning(f"Schema migration warning: {e}")
        await conn.run_sync(Base.metadata.create_all)
    # Seed/Update units in database
    from services.common.database import async_session
    async with async_session() as session:
        result = await session.execute(select(models.Unit))
        existing_units = {u.name for u in result.scalars().all()}
        initial_units = [
            "BAN", "BAT", "CHA", "CHH", "KAM", "KAN", "KANZ1", "KOH", "KRA",
            "MON", "ODD", "PNP", "PNPZ1", "PNPZ2", "PRE", "PRH", "PUR", "ROT",
            "SIE", "SIH", "SPE", "STU", "SVA", "TAK", "THO"
        ]
        new_units = [u for u in initial_units if u not in existing_units]
        if new_units:
            logger.info(f"Seeding missing units to the database: {new_units}")
            for unit_name in new_units:
                db_unit = models.Unit(name=unit_name, description=f"GIS Unit for {unit_name}")
                session.add(db_unit)
            await session.commit()
            logger.info("Missing units seeded successfully.")

    # Initialize Cache connection
    await cache.connect()
    yield

app = FastAPI(
    title="GIS Asset Microservice",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CRUD HELPERS ---
async def get_store_item(db: AsyncSession, key: str):
    result = await db.execute(select(models.GISStore).where(models.GISStore.key == key))
    return result.scalar_one_or_none()

async def upsert_store_item(db: AsyncSession, key: str, value: str):
    result = await db.execute(select(models.GISStore).where(models.GISStore.key == key))
    db_item = result.scalar_one_or_none()
    if db_item:
        # Always update value
        db_item.value = value
        # If previous status was completed or cleared, reset it to draft
        if db_item.status != "draft":
            logger.info(f"Key '{key}' was in '{db_item.status}' status. Overwriting and resetting to 'draft'.")
            db_item.status = "draft"
            db_item.result = None
        db_item.version += 1
    else:
        db_item = models.GISStore(key=key, value=value, status="draft", version=1)
        db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    return db_item

async def delete_store_item(db: AsyncSession, key: str):
    result = await db.execute(select(models.GISStore).where(models.GISStore.key == key))
    db_item = result.scalar_one_or_none()
    if db_item:
        await db.delete(db_item)
        await db.commit()
        return True
    return False

# --- API ENDPOINTS ---

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "asset"}

# Key-Value Store Endpoints with Cache Integration
@app.get("/store/{key}", response_model=schemas.GISStore)
async def get_store_value(key: str, db: AsyncSession = Depends(get_db)):
    # 1. Read status and payload from Redis Cache
    status_val = await cache.get(f"store:{key}:status")
    if status_val:
        status_str = status_val.decode('utf-8')
        cached_val = await cache.get(f"store:{key}:{status_str}")
        if cached_val:
            logger.info(f"Redis Cache HIT for key: {key} with status: {status_str}")
            cached_data = json.loads(cached_val)
            return schemas.GISStore(
                key=key,
                value=cached_data["value"],
                status=status_str,
                result=cached_data.get("result"),
                updated_at=datetime.fromisoformat(cached_data["updated_at"]),
                version=cached_data["version"]
            )

    # 2. Database Fallback on Cache Miss
    logger.info(f"Redis Cache MISS for key: {key}. Querying database.")
    db_item = await get_store_item(db, key)
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in store."
        )

    # 3. Write to Cache
    payload = {
        "value": db_item.value,
        "result": db_item.result,
        "updated_at": db_item.updated_at.isoformat(),
        "version": db_item.version
    }
    await cache.set(f"store:{key}:status", db_item.status, ex=3600)
    await cache.set(f"store:{key}:{db_item.status}", json.dumps(payload), ex=3600)
    return db_item

@app.post("/store", response_model=schemas.GISStore)
async def upsert_store_value(payload: schemas.GISStoreCreate, db: AsyncSession = Depends(get_db)):
    db_item = await upsert_store_item(db, key=payload.key, value=payload.value)
    
    # Invalidate old caches
    await cache.delete(f"store:{payload.key}:status")
    await cache.delete(f"store:{payload.key}:draft")
    await cache.delete(f"store:{payload.key}:completed")
    await cache.delete(f"store:{payload.key}:cleared")

    # Update cache
    cache_payload = {
        "value": db_item.value,
        "result": db_item.result,
        "updated_at": db_item.updated_at.isoformat(),
        "version": db_item.version
    }
    await cache.set(f"store:{payload.key}:status", db_item.status, ex=3600)
    await cache.set(f"store:{payload.key}:{db_item.status}", json.dumps(cache_payload), ex=3600)
    logger.info(f"Database write and Cache update completed for key: {payload.key}")
    return db_item

@app.delete("/store/{key}")
async def delete_store_value(key: str, db: AsyncSession = Depends(get_db)):
    success = await delete_store_item(db, key)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in store."
        )
    # Clear all caches
    await cache.delete(f"store:{key}:status")
    await cache.delete(f"store:{key}:draft")
    await cache.delete(f"store:{key}:completed")
    await cache.delete(f"store:{key}:cleared")
    logger.info(f"Database deletion and Cache clearance completed for key: {key}")
    return {"detail": f"Key '{key}' deleted successfully"}

@app.post("/store/{key}/complete", response_model=schemas.GISStore)
async def complete_store_value(key: str, db: AsyncSession = Depends(get_db)):
    db_item = await get_store_item(db, key)
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in store."
        )
    
    db_item.status = "completed"
    db_item.result = json.dumps({
        "result": "completed",
        "timestamp": datetime.utcnow().isoformat()
    })
    db_item.version += 1
    await db.commit()
    await db.refresh(db_item)
    
    # Invalidate and update cache
    await cache.delete(f"store:{key}:status")
    await cache.delete(f"store:{key}:draft")
    await cache.delete(f"store:{key}:completed")
    await cache.delete(f"store:{key}:cleared")
    
    cache_payload = {
        "value": db_item.value,
        "result": db_item.result,
        "updated_at": db_item.updated_at.isoformat(),
        "version": db_item.version
    }
    await cache.set(f"store:{key}:status", "completed", ex=3600)
    await cache.set(f"store:{key}:completed", json.dumps(cache_payload), ex=3600)
    return db_item

@app.post("/store/{key}/clear", response_model=schemas.GISStore)
async def clear_store_value(key: str, db: AsyncSession = Depends(get_db)):
    db_item = await get_store_item(db, key)
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in store."
        )
    
    db_item.status = "cleared"
    db_item.result = json.dumps({
        "result": "cleared",
        "timestamp": datetime.utcnow().isoformat()
    })
    db_item.version += 1
    await db.commit()
    await db.refresh(db_item)
    
    # Invalidate and update cache
    await cache.delete(f"store:{key}:status")
    await cache.delete(f"store:{key}:draft")
    await cache.delete(f"store:{key}:completed")
    await cache.delete(f"store:{key}:cleared")
    
    cache_payload = {
        "value": db_item.value,
        "result": db_item.result,
        "updated_at": db_item.updated_at.isoformat(),
        "version": db_item.version
    }
    await cache.set(f"store:{key}:status", "cleared", ex=3600)
    await cache.set(f"store:{key}:cleared", json.dumps(cache_payload), ex=3600)
    return db_item

@app.get("/store/{key}/latest", response_model=schemas.GISStore)
async def get_latest_store_value(key: str, db: AsyncSession = Depends(get_db)):
    return await get_store_value(key, db)

@app.get("/store/{key}/completed", response_model=schemas.GISStore)
async def get_completed_store_value(key: str, db: AsyncSession = Depends(get_db)):
    # Try reading from cache
    cached_val = await cache.get(f"store:{key}:completed")
    if cached_val:
        logger.info(f"Redis Cache HIT for completed key: {key}")
        cached_data = json.loads(cached_val)
        return schemas.GISStore(
            key=key,
            value=cached_data["value"],
            status="completed",
            result=cached_data.get("result"),
            updated_at=datetime.fromisoformat(cached_data["updated_at"]),
            version=cached_data["version"]
        )
    
    db_item = await get_store_item(db, key)
    if not db_item or db_item.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Completed key '{key}' not found or not in completed status."
        )
    
    cache_payload = {
        "value": db_item.value,
        "result": db_item.result,
        "updated_at": db_item.updated_at.isoformat(),
        "version": db_item.version
    }
    await cache.set(f"store:{key}:completed", json.dumps(cache_payload), ex=3600)
    return db_item

@app.get("/store/{key}/status")
async def get_store_status(key: str, db: AsyncSession = Depends(get_db)):
    db_item = await get_store_item(db, key)
    if not db_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in store."
        )
    return {"status": db_item.status}

# Units Endpoints
@app.get("/units", response_model=list[schemas.Unit])
async def get_units(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Unit).offset(skip).limit(limit))
    return result.scalars().all()

@app.post("/units", response_model=schemas.Unit, status_code=status.HTTP_201_CREATED)
async def create_unit(payload: schemas.UnitCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.Unit).where(models.Unit.name == payload.name))
    existing_unit = result.scalar_one_or_none()
    if existing_unit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unit with name '{payload.name}' already exists."
        )
    db_unit = models.Unit(name=payload.name, description=payload.description)
    db.add(db_unit)
    await db.commit()
    await db.refresh(db_unit)
    return db_unit

# KPIs Raw Records
@app.get("/kpi_records", response_model=list[schemas.KPI])
async def get_kpi_records(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.KPI).options(selectinload(models.KPI.unit)).offset(skip).limit(limit)
    )
    return result.scalars().all()

@app.post("/kpi_records", response_model=schemas.KPI, status_code=status.HTTP_201_CREATED)
async def create_kpi_record(payload: schemas.KPICreate, db: AsyncSession = Depends(get_db)):
    db_kpi = models.KPI(
        name=payload.name,
        value=payload.value,
        unit_id=payload.unit_id
    )
    db.add(db_kpi)
    await db.commit()
    await db.refresh(db_kpi, attribute_names=["unit"])
    return db_kpi
