from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from app.telegram_bot import telegram_bot, TelegramBot

router = APIRouter(prefix="/telegram", tags=["Telegram"])

class TelegramMessageRequest(BaseModel):
    text: str
    chat_id: Optional[str] = None
    token: Optional[str] = None

@router.post("/send")
async def send_message(payload: TelegramMessageRequest):
    """
    Send a direct message through the Telegram Bot to the default or specified Chat ID.
    If a token is provided in the request body, it will override the default server token.
    """
    if payload.token:
        # Create a temporary bot instance using the custom token provided by the client
        custom_bot = TelegramBot(token=payload.token)
        success = await custom_bot.send_message(payload.text, chat_id=payload.chat_id)
    else:
        # Fall back to the default bot configured in the server's .env
        success = await telegram_bot.send_message(payload.text, chat_id=payload.chat_id)
        
    return {
        "success": success,
        "message": "Message sent successfully" if success else "Failed to send message (check credentials and configuration)"
    }

@router.post("/webhook")
async def handle_webhook(update: dict, background_tasks: BackgroundTasks):
    """
    Webhook endpoint to receive real-time updates from Telegram. (Placeholder)
    """
    return {"status": "received"}
