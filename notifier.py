"""
Telegram notification system
"""

import asyncio
import logging
from typing import List, Optional
from datetime import datetime
import aiohttp

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram Bot API"""
    
    def __init__(self, config):
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{config.telegram_token}"
        self.chat_id = config.telegram_chat_id
        self.session: Optional[aiohttp.ClientSession] = None
        self.message_count = 0
    
    async def initialize(self) -> None:
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
        logger.info("Telegram notifier initialized")
    
    async def close(self) -> None:
        """Close HTTP session"""
        if self.session:
            await self.session.close()
    
    async def send_message(
        self,
        text: str,
        parse_mode: str = "Markdown",
        disable_preview: bool = True
    ) -> bool:
        """Send message to Telegram"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview
        }
        
        for attempt in range(self.config.max_retries):
            try:
                async with self.session.post(url, json=payload) as response:
                    if response.status == 200:
                        self.message_count += 1
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"Telegram API error: {response.status} - {error}")
                        
            except Exception as e:
                logger.error(f"Send failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))
        
        return False
    
    async def send_booking_alert(
        self,
        movie_name: str,
        theaters: List,
        movie_url: str
    ) -> bool:
        """Send booking availability alert"""
        if not theaters:
            return False
        
        # Sort by priority
        sorted_theaters = sorted(theaters, key=lambda t: (t.priority, t.name))
        
        # Build message
        message = (
            "🚨 *BOOKING ALERT* 🚨\n\n"
            "✨ *New availability detected!* ✨\n\n"
            f"🎬 *{movie_name}*\n\n"
        )
        
        for idx, theater in enumerate(sorted_theaters, 1):
            stars = "⭐" * theater.priority
            message += f"{idx}. {stars} *{theater.name}*\n"
            
            if theater.location:
                message += f"   📍 _{theater.location}_\n"
            
            # Available times
            available = [st for st in theater.showtimes if st.available]
            if available:
                times = [st.time for st in available[:6]]
                time_str = ", ".join(times)
                if len(available) > 6:
                    time_str += f" +{len(available) - 6} more"
                message += f"   🎬 {time_str}\n"
            
            message += "\n"
        
        message += (
            f"🔗 [Book Now]({movie_url})\n\n"
            f"⏰ {datetime.now().strftime('%I:%M %p, %d %b')}"
        )
        
        return await self.send_message(message)
    
    async def send_error_alert(self, error: str) -> bool:
        """Send error notification"""
        message = (
            "⚠️ *DistrictWatch Error*\n\n"
            f"Error: `{error}`\n\n"
            f"⏰ {datetime.now().strftime('%I:%M %p, %d %b')}\n\n"
            "Will retry automatically..."
        )
        return await self.send_message(message)
    
    async def send_circuit_breaker_alert(self, state: str) -> bool:
        """Send circuit breaker status"""
        if state == "OPEN":
            message = (
                "🛑 *Circuit Breaker Activated*\n\n"
                "Too many consecutive failures.\n"
                "Pausing requests temporarily.\n\n"
                f"⏰ {datetime.now().strftime('%I:%M %p, %d %b')}"
            )
        else:
            message = (
                "✅ *Circuit Breaker Reset*\n\n"
                "System recovered. Monitoring resumed.\n\n"
                f"⏰ {datetime.now().strftime('%I:%M %p, %d %b')}"
            )
        return await self.send_message(message)
