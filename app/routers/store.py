from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import schemas, crud

router = APIRouter(prefix="/store", tags=["GIS Store"])

_store_cache = {}

@router.get("/{key}", response_model=schemas.GISStore)
async def get_store_value(key: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieve a value by its storage key from the backend database (cached).
    """
    if key in _store_cache:
        return _store_cache[key]

    item = await crud.get_store_value(db, key=key)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in store."
        )
    schema_item = schemas.GISStore.model_validate(item)
    _store_cache[key] = schema_item
    return schema_item

@router.post("", response_model=schemas.GISStore, status_code=status.HTTP_200_OK)
@router.post("/", response_model=schemas.GISStore, status_code=status.HTTP_200_OK)
async def upsert_store_value(payload: schemas.GISStoreCreate, db: AsyncSession = Depends(get_db)):
    """
    Save or update a key-value storage pair (handles both /api/store and /api/store/).
    """
    item = await crud.upsert_store_value(db, item=payload)
    schema_item = schemas.GISStore.model_validate(item)
    _store_cache[payload.key] = schema_item
    return schema_item

@router.post("/{key}/complete", response_model=schemas.GISStore, status_code=status.HTTP_200_OK)
async def complete_store_value(key: str, db: AsyncSession = Depends(get_db)):
    """
    Mark a storage key as completed.
    """
    item = await crud.complete_store_value(db, key=key)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key '{key}' not found in store."
        )
    schema_item = schemas.GISStore.model_validate(item)
    _store_cache[key] = schema_item
    return schema_item

@router.delete("/{key}", status_code=status.HTTP_200_OK)
async def delete_store_value(key: str, db: AsyncSession = Depends(get_db)):
    """
    Delete a storage key-value pair.
    """
    _store_cache.pop(key, None)
    await crud.delete_store_value(db, key=key)
    return {"detail": f"Key '{key}' deleted successfully"}
