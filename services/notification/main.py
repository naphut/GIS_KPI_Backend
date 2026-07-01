import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from services.common.database import engine, Base, get_db, settings, async_session
from services.common import models, schemas
import httpx
import json
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification_service")

# --- Telegram Bot Helper Class ---
class TelegramBot:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.default_chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, text: str, chat_id: str = None) -> bool:
        target_chat_id = chat_id or self.default_chat_id
        if not self.token or not target_chat_id or "your_telegram" in self.token:
            logger.warning("Telegram Bot token or Chat ID not configured. Skipping message send.")
            return False

        # Telegram character limit is 4096. We split at 3900 to leave safety margin.
        if len(text) <= 3900:
            return await self._send_single_message(text, target_chat_id)

        logger.info(f"Message too long ({len(text)} characters). Splitting into chunks...")
        
        # Split by lines
        lines = text.split("\n")
        chunks = []
        current_chunk = ""
        for line in lines:
            if len(current_chunk) + len(line) + 1 > 3900:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = line + "\n"
            else:
                current_chunk += line + "\n"
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        success = True
        for i, chunk in enumerate(chunks):
            # Append page number
            if len(chunks) > 1:
                chunk += f"\n\n📄 <b>Part {i+1}/{len(chunks)}</b>"
            res = await self._send_single_message(chunk, target_chat_id)
            if not res:
                success = False
            # Small delay to prevent rate limits
            if i < len(chunks) - 1:
                await asyncio.sleep(0.5)
        return success

    async def _send_single_message(self, text: str, target_chat_id: str) -> bool:
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=10.0)
                if response.status_code == 200:
                    return True
                logger.error(f"Failed to send Telegram message: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Exception occurred while sending Telegram message: {e}")
            return False

telegram_bot = TelegramBot()

# --- Startup Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Notification Microservice Database initialized.")

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

    yield

app = FastAPI(
    title="GIS Notification Microservice",
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

# --- REQUEST SCHEMAS ---
class TelegramMessageRequest(BaseModel):
    text: str
    chat_id: Optional[str] = None
    token: Optional[str] = None

# --- API ENDPOINTS ---

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "notification"}

# Telegram routes
@app.post("/telegram/send")
async def send_message(payload: TelegramMessageRequest):
    if payload.token:
        custom_bot = TelegramBot(token=payload.token)
        success = await custom_bot.send_message(payload.text, chat_id=payload.chat_id)
    else:
        success = await telegram_bot.send_message(payload.text, chat_id=payload.chat_id)
        
    return {
        "success": success,
        "message": "Message sent successfully" if success else "Failed to send message"
    }

class TelegramSendLatestRequest(BaseModel):
    key: str
    chat_id: Optional[str] = None
    token: Optional[str] = None

@app.post("/telegram/send-latest")
async def send_latest_telegram(payload: TelegramSendLatestRequest):
    # 1. Fetch data from Asset Microservice
    asset_url = f"http://127.0.0.1:8001/store/{payload.key}"
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(asset_url, timeout=10.0)
            if res.status_code != 200:
                return {
                    "success": False,
                    "message": f"Store key '{payload.key}' not found or error retrieving it."
                }
            store_data = res.json()
    except Exception as e:
        logger.error(f"Failed to fetch store key '{payload.key}' from Asset microservice: {e}")
        return {
            "success": False,
            "message": f"Connection error fetching store key: {e}"
        }

    status_str = store_data.get("status")
    if status_str not in ("completed", "cleared"):
        return {
            "success": False,
            "message": f"No completed or cleared data found. Current status is '{status_str}'."
        }

    # 2. Parse value and build HTML message
    raw_val = store_data.get("value")
    try:
        value_data = json.loads(raw_val)
    except Exception:
        value_data = raw_val

    # Create html message
    message = f"📊 <b>GIS KPI STATUS UPDATE</b>\n"
    message += f"🔑 <b>Key:</b> {payload.key}\n"
    message += f"🚦 <b>Status:</b> {status_str.upper()} ✅\n"
    if store_data.get("result"):
        try:
            res_obj = json.loads(store_data["result"])
            message += f"⏰ <b>Timestamp:</b> {res_obj.get('timestamp', '-')}\n"
        except Exception:
            pass
    message += "\n"

    if isinstance(value_data, list):
        message += f"📋 <b>Total Records:</b> {len(value_data)}\n"
        if len(value_data) > 0:
            message += f"\n<b>Items:</b>\n"
            for i, item in enumerate(value_data):
                code = item.get("code") or item.get("importRequestCode") or item.get("requestExportCode") or "-"
                unit = item.get("unit") or "-"
                message += f"{i+1}. <code>{code}</code> (Unit: {unit})\n"
    elif isinstance(value_data, dict):
        message += f"📝 <b>Summary Details:</b>\n"
        for k, v in value_data.items():
            message += f"• {k}: {v}\n"

    # 3. Send message to Telegram
    bot_token = payload.token or settings.TELEGRAM_BOT_TOKEN
    target_chat_id = payload.chat_id or settings.TELEGRAM_CHAT_ID

    if not bot_token or not target_chat_id or "your_telegram" in bot_token:
        return {
            "success": False,
            "message": "Telegram configuration missing or invalid. Bot token/Chat ID not set.",
            "data": store_data
        }

    bot = TelegramBot(token=bot_token, chat_id=target_chat_id)
    success = await bot.send_message(message)

    return {
        "success": success,
        "message": "Latest completed data sent successfully" if success else "Failed to send message",
        "data": store_data
    }

@app.post("/telegram/webhook")
async def handle_webhook(update: dict):
    return {"status": "received"}

# Note Templates CRUD routes
@app.get("/templates", response_model=list[schemas.TelegramTemplate])
async def get_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.TelegramTemplate).order_by(models.TelegramTemplate.created_at.desc()))
    return result.scalars().all()

@app.post("/templates", response_model=schemas.TelegramTemplate, status_code=status.HTTP_201_CREATED)
async def create_template(payload: schemas.TelegramTemplateCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.TelegramTemplate).where(models.TelegramTemplate.content == payload.content))
    existing_template = result.scalar_one_or_none()
    if existing_template:
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Template with this content already exists."
         )
    db_template = models.TelegramTemplate(content=payload.content)
    db.add(db_template)
    await db.commit()
    await db.refresh(db_template)
    return db_template

@app.delete("/templates/{template_id}")
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.TelegramTemplate).where(models.TelegramTemplate.id == template_id))
    db_template = result.scalar_one_or_none()
    if not db_template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found."
        )
    await db.delete(db_template)
    await db.commit()
    return {"detail": "Template deleted successfully"}
