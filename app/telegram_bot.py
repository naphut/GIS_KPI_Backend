import httpx
import logging
from app.database import settings

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN
        self.default_chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, text: str, chat_id: str = None) -> bool:
        """
        Sends an HTML-formatted message to the specified chat ID or the default chat ID.
        """
        target_chat_id = chat_id or self.default_chat_id
        if not self.token or not target_chat_id or "your_telegram" in self.token:
            logger.warning("Telegram Bot token or Chat ID not configured. Skipping message send.")
            return False

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

# Export a default instance for easy reuse
telegram_bot = TelegramBot()
