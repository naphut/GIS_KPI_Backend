from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import schemas, crud

router = APIRouter(prefix="/store", tags=["GIS Store"])

@router.get("/{key}", response_model=schemas.GISStore)
async def get_store_value(key: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a value by its storage key from the backend database.
    """
    item = await crud.get_store_value(db, key=key)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in store."
        )
    return item

@router.post("/", response_model=schemas.GISStore, status_code=status.HTTP_200_OK)
async def upsert_store_value(payload: schemas.GISStoreCreate, db: AsyncSession = Depends(get_db)):
    """
    Save or update a key-value storage pair.
    """
    return await crud.upsert_store_value(db, item=payload)

@router.delete("/{key}", status_code=status.HTTP_200_OK)
async def delete_store_value(key: str, db: AsyncSession = Depends(get_db)):
    """
    Delete a storage key-value pair.
    """
    success = await crud.delete_store_value(db, key=key)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in store."
        )
    return {"detail": f"Key '{key}' deleted successfully"}
