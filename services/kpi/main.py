import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from services.common import schemas
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kpi_service")

# Address of the asset microservice
ASSET_SERVICE_URL = "http://127.0.0.1:8001"

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("KPI Microservice initialized.")
    yield

app = FastAPI(
    title="GIS KPI Microservice",
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

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "kpi"}

@app.get("/kpis", response_model=list[schemas.KPI])
async def get_kpis(skip: int = 0, limit: int = 100):
    """
    Retrieve all KPIs by making an async service-to-service request to the Asset Service.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ASSET_SERVICE_URL}/kpi_records", 
                params={"skip": skip, "limit": limit},
                timeout=5.0
            )
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Asset microservice error: {response.text}"
                )
            return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch KPIs from Asset Service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"KPI service-to-service communication failure: {e}"
        )

@app.post("/kpis", response_model=schemas.KPI, status_code=status.HTTP_201_CREATED)
async def create_kpi(payload: schemas.KPICreate):
    """
    Create a new KPI by verifying the unit and posting to the Asset Service.
    """
    try:
        async with httpx.AsyncClient() as client:
            # 1. Verify if the unit exists via Asset Service
            units_res = await client.get(f"{ASSET_SERVICE_URL}/units", timeout=5.0)
            if units_res.status_code != 200:
                raise HTTPException(
                    status_code=units_res.status_code,
                    detail="Failed to query units from Asset microservice."
                )
            
            units = units_res.json()
            unit_exists = any(u["id"] == payload.unit_id for u in units)
            if not unit_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Unit with ID {payload.unit_id} does not exist in Asset Service."
                )
            
            # 2. Post KPI record creation
            kpi_res = await client.post(
                f"{ASSET_SERVICE_URL}/kpi_records",
                json=payload.model_dump() if hasattr(payload, "model_dump") else payload.dict(),
                timeout=5.0
            )
            if kpi_res.status_code != 201:
                raise HTTPException(
                    status_code=kpi_res.status_code,
                    detail=f"Failed to create KPI record: {kpi_res.text}"
                )
            return kpi_res.json()
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"KPI creation service-to-service call failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"KPI service communication failure: {e}"
        )
