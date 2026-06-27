from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app import schemas, crud

router = APIRouter(prefix="/templates", tags=["Telegram Templates"])

@router.get("/", response_model=list[schemas.TelegramTemplate])
async def get_templates(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """
    Retrieve all Telegram message templates.
    """
    templates = await crud.get_templates(db, skip=skip, limit=limit)
    return templates

@router.post("/", response_model=schemas.TelegramTemplate, status_code=status.HTTP_201_CREATED)
async def create_template(payload: schemas.TelegramTemplateCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new Telegram message template.
    """
    existing = await crud.get_template_by_content(db, content=payload.content)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Template with this content already exists."
        )
    return await crud.create_template(db, template=payload)

@router.delete("/{template_id}", status_code=status.HTTP_200_OK)
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """
    Delete a Telegram message template.
    """
    success = await crud.delete_template(db, template_id=template_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template with ID {template_id} does not exist."
        )
    return {"detail": "Template deleted successfully"}
