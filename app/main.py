import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.future import select

from app.database import engine, Base, async_session
from app import models
from app.routers import kpi, telegram, units, templates, store

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up FastAPI application...")
    try:
        # Verify connection and create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified/created successfully.")
            
        # Seed units if none exist
        async with async_session() as session:
            result = await session.execute(select(models.Unit))
            existing_units = result.scalars().all()
            if not existing_units:
                logger.info("Seeding units to the database...")
                initial_units = [
                    "BAN", "BAT", "CHA", "CHH", "KAM", "KAN", "KANZ1", "KOH", "KRA",
                    "MON", "ODD", "PNP", "PNPZ1", "PNPZ2", "PRE", "PRH", "PUR", "ROT",
                    "SIE", "SIH", "SPE", "STU", "SVA", "TAK", "THO"
                ]
                for unit_name in initial_units:
                    db_unit = models.Unit(name=unit_name, description=f"GIS Unit for {unit_name}")
                    session.add(db_unit)
                await session.commit()
                logger.info("Units seeded successfully.")

            # Seed templates if none exist
            async with async_session() as session:
                result = await session.execute(select(models.TelegramTemplate))
                existing_templates = result.scalars().all()
                if not existing_templates:
                    logger.info("Seeding default templates to the database...")
                    initial_templates = [
                        "Please prioritize these items!",
                        "All items signed and completed.",
                        "Kindly check and confirm, thank you!"
                    ]
                    for template_content in initial_templates:
                        db_template = models.TelegramTemplate(content=template_content)
                        session.add(db_template)
                    await session.commit()
                    logger.info("Default templates seeded successfully.")
    except Exception as e:
        logger.warning(
            f"Could not connect to the database or seed on startup: {e}. "
            "Please check that your PostgreSQL service is running and DATABASE_URL in .env is correct."
        )
    yield
    logger.info("Shutting down FastAPI application...")

app = FastAPI(
    title="GIS Backend API",
    description="FastAPI Backend for GIS KPI tracking and Telegram bot integration.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins in development
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Include Routers with an "/api" prefix
app.include_router(kpi.router, prefix="/api")
app.include_router(telegram.router, prefix="/api")
app.include_router(units.router, prefix="/api")
app.include_router(templates.router, prefix="/api")
app.include_router(store.router, prefix="/api")

@app.get("/", tags=["General"])
async def root():
    return {
        "title": "GIS Backend API",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health", tags=["General"])
async def health():
    return {"status": "healthy"}
