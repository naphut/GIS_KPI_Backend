from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import schemas, crud

router = APIRouter(prefix="/units", tags=["Units"])

@router.get("/", response_model=list[schemas.Unit])
async def get_units(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """
    Retrieve all units.
    """
    units = await crud.get_units(db, skip=skip, limit=limit)
    return units

@router.post("/", response_model=schemas.Unit, status_code=status.HTTP_201_CREATED)
async def create_unit(payload: schemas.UnitCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new unit.
    """
    existing_unit = await crud.get_unit_by_name(db, name=payload.name)
    if existing_unit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unit with name '{payload.name}' already exists."
        )
    return await crud.create_unit(db, unit=payload)
