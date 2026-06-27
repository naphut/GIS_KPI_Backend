from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import schemas, crud

router = APIRouter(prefix="/kpis", tags=["KPIs"])

@router.get("/", response_model=list[schemas.KPI])
async def get_kpis(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """
    Retrieve all KPIs.
    """
    kpis = await crud.get_kpis(db, skip=skip, limit=limit)
    return kpis

@router.post("/", response_model=schemas.KPI, status_code=status.HTTP_201_CREATED)
async def create_kpi(payload: schemas.KPICreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new KPI.
    """
    # Check if the unit exists before creating the KPI record
    unit = await crud.get_unit_by_id(db, unit_id=payload.unit_id)
    if not unit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unit with ID {payload.unit_id} does not exist."
        )
    return await crud.create_kpi(db, kpi=payload)
