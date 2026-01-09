"""
Telegram command handler for dynamic movie/theatre management
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handle Telegram bot commands"""
    
    def __init__(self, config, notifier):
        self.config = config
        self.notifier = notifier
        self.commands = {
            '/start': self.cmd_start,
            '/help': self.cmd_help,
            '/add': self.cmd_add,
            '/remove': self.cmd_remove,
            '/list': self.cmd_list,
            '/enable': self.cmd_enable,
            '/disable': self.cmd_disable,
            '/status': self.cmd_status,
            '/theaters': self.cmd_theaters,
            '/addtheater': self.cmd_add_theater,
            '/removetheater': self.cmd_remove_theater,
        }
    
    async def handle_update(self, update: Dict) -> None:
        """Process incoming Telegram update"""
        try:
            message = update.get('message', {})
            text = message.get('text', '').strip()
            
            if not text or not text.startswith('/'):
                return
            
            # Parse command and arguments
            parts = text.split(maxsplit=1)
            command = parts[0].lower().split('@')[0]  # Remove @botname suffix
            args = parts[1] if len(parts) > 1 else ""
            
            handler = self.commands.get(command)
            if handler:
                await handler(args)
            else:
                await self.send_reply(f"❌ Unknown command: {command}\nUse /help for available commands")
                
        except Exception as e:
            logger.error(f"Error handling command: {e}")
            await self.send_reply(f"❌ Error: {str(e)}")
    
    async def send_reply(self, text: str) -> None:
        """Send reply message"""
        await self.notifier.send_message(text)
    
    async def cmd_start(self, args: str) -> None:
        """Welcome message"""
        await self.send_reply(
            "🎬 *Welcome to DistrictWatch!*\n\n"
            "I monitor movie bookings on District.in and send instant alerts.\n\n"
            "*Quick Start:*\n"
            "1️⃣ Add a movie: `/add <url> <name> <city>`\n"
            "2️⃣ View movies: `/list`\n"
            "3️⃣ Manage theaters: `/theaters <movie_id>`\n\n"
            "Use /help for all commands."
        )
    
    async def cmd_help(self, args: str) -> None:
        """Show all commands"""
        await self.send_reply(
            "📚 *DistrictWatch Commands*\n\n"
            "*🎬 Movie Management:*\n"
            "`/add <url> <name> [city]` - Add movie\n"
            "`/remove <id>` - Remove movie\n"
            "`/list` - List all movies\n"
            "`/enable <id>` - Enable monitoring\n"
            "`/disable <id>` - Pause monitoring\n\n"
            "*🎭 Theater Management:*\n"
            "`/theaters <id>` - Show movie's theaters\n"
            "`/addtheater <id> <name>` - Add theater\n"
            "`/removetheater <id> <name>` - Remove theater\n\n"
            "*📊 Information:*\n"
            "`/status` - System status\n"
            "`/help` - This help message\n\n"
            "*Example:*\n"
            "```\n"
            "/add https://district.in/movies/leo-... Leo Chennai\n"
            "/theaters leo_chennai\n"
            "/addtheater leo_chennai SPI Cinemas\n"
            "```"
        )
    
    async def cmd_add(self, args: str) -> None:
        """Add a movie"""
        if not args:
            await self.send_reply(
                "❌ *Usage:* `/add <url> <name> [city]`\n\n"
                "*Example:*\n"
                "`/add https://district.in/movies/leo-... Leo Chennai`\n\n"
                "City defaults to Chennai if not specified."
            )
            return
        
        try:
            parts = args.split()
            if len(parts) < 2:
                await self.send_reply("❌ Please provide both URL and movie name")
                return
            
            url = parts[0]
            
            # Validate URL
            if not ("district.in/movies/" in url or "district.in/events/" in url):
                await self.send_reply("❌ Invalid URL. Must be from district.in")
                return
            
            # Detect city from last word or URL
            known_cities = ['chennai', 'bangalore', 'bengaluru', 'hyderabad', 'mumbai', 
                          'delhi', 'pune', 'kolkata', 'kochi', 'coimbatore']
            
            if parts[-1].lower() in known_cities:
                city = parts[-1].capitalize()
                name = ' '.join(parts[1:-1])
            else:
                # Try to extract city from URL
                city = "Chennai"
                for c in known_cities:
                    if c in url.lower():
                        city = c.capitalize()
                        break
                name = ' '.join(parts[1:])
            
            if not name:
                await self.send_reply("❌ Movie name cannot be empty")
                return
            
            movie_id = self.config.add_movie(url, name, city)
            
            await self.send_reply(
                "✅ *Movie Added!*\n\n"
                f"🎬 *{name}*\n"
                f"📍 City: {city}\n"
                f"🆔 ID: `{movie_id}`\n"
                f"🎭 Theaters: {len(self.config.default_theaters)}\n\n"
                f"Use `/theaters {movie_id}` to customize theaters."
            )
            
            logger.info(f"Movie added: {movie_id}")
            
        except Exception as e:
            logger.error(f"Error adding movie: {e}")
            await self.send_reply(f"❌ Error: {str(e)}")
    
    async def cmd_remove(self, args: str) -> None:
        """Remove a movie"""
        if not args:
            await self.send_reply("❌ *Usage:* `/remove <movie_id>`\n\nUse /list to see movie IDs")
            return
        
        movie_id = args.strip().lower()
        movie = self.config.get_movie(movie_id)
        
        if not movie:
            await self.send_reply(f"❌ Movie not found: `{movie_id}`\n\nUse /list to see available movies")
            return
        
        name = movie.movie_name
        if self.config.remove_movie(movie_id):
            await self.send_reply(f"✅ *Removed:* {name}\n\nMonitoring stopped.")
            logger.info(f"Movie removed: {movie_id}")
        else:
            await self.send_reply("❌ Failed to remove movie")
    
    async def cmd_list(self, args: str) -> None:
        """List all movies"""
        movies = self.config.list_movies()
        
        if not movies:
            await self.send_reply(
                "📝 *No movies configured*\n\n"
                "Use `/add <url> <name> <city>` to add your first movie!"
            )
            return
        
        lines = ["📽️ *Configured Movies*\n"]
        
        for idx, m in enumerate(movies, 1):
            status = "✅" if m['enabled'] else "⏸️"
            lines.append(
                f"{idx}. {status} *{m['name']}* ({m['city']})\n"
                f"   🆔 `{m['id']}`\n"
                f"   🎭 {m['theaters']} theaters\n"
            )
        
        lines.append("\n💡 Use `/theaters <id>` to view/edit theaters")
        await self.send_reply('\n'.join(lines))
    
    async def cmd_enable(self, args: str) -> None:
        """Enable movie"""
        if not args:
            await self.send_reply("❌ *Usage:* `/enable <movie_id>`")
            return
        
        movie_id = args.strip().lower()
        movie = self.config.get_movie(movie_id)
        
        if not movie:
            await self.send_reply(f"❌ Movie not found: `{movie_id}`")
            return
        
        if self.config.enable_movie(movie_id):
            await self.send_reply(f"✅ *Enabled:* {movie.movie_name}\n\nMonitoring resumed.")
            logger.info(f"Movie enabled: {movie_id}")
    
    async def cmd_disable(self, args: str) -> None:
        """Disable movie"""
        if not args:
            await self.send_reply("❌ *Usage:* `/disable <movie_id>`")
            return
        
        movie_id = args.strip().lower()
        movie = self.config.get_movie(movie_id)
        
        if not movie:
            await self.send_reply(f"❌ Movie not found: `{movie_id}`")
            return
        
        if self.config.disable_movie(movie_id):
            await self.send_reply(f"⏸️ *Paused:* {movie.movie_name}\n\nUse /enable to resume.")
            logger.info(f"Movie disabled: {movie_id}")
    
    async def cmd_status(self, args: str) -> None:
        """Show system status"""
        active = self.config.get_active_movies()
        total = len(self.config.movies)
        
        msg = (
            "📊 *System Status*\n\n"
            f"📽️ Active movies: {len(active)}/{total}\n"
            f"🎭 Default theaters: {len(self.config.default_theaters)}\n"
            f"⏱️ Check interval: {self.config.check_interval}s\n\n"
        )
        
        if active:
            msg += "*Currently Monitoring:*\n"
            for m in active[:5]:
                msg += f"• {m.movie_name} ({m.city})\n"
            if len(active) > 5:
                msg += f"• ... and {len(active) - 5} more\n"
        else:
            msg += "_No movies being monitored_\n"
        
        msg += f"\n⏰ {datetime.now().strftime('%I:%M %p, %d %b %Y')}"
        await self.send_reply(msg)
    
    async def cmd_theaters(self, args: str) -> None:
        """Show theaters for a movie"""
        if not args:
            await self.send_reply(
                "❌ *Usage:* `/theaters <movie_id>`\n\n"
                "Use /list to see movie IDs"
            )
            return
        
        movie_id = args.strip().lower()
        movie = self.config.get_movie(movie_id)
        
        if not movie:
            await self.send_reply(f"❌ Movie not found: `{movie_id}`")
            return
        
        if not movie.target_theaters:
            await self.send_reply(
                f"🎭 *Theaters for {movie.movie_name}*\n\n"
                "_No theaters configured_\n\n"
                f"Use `/addtheater {movie_id} <theater_name>` to add one"
            )
            return
        
        lines = [f"🎭 *Theaters for {movie.movie_name}*\n"]
        
        sorted_theaters = sorted(movie.target_theaters, key=lambda t: t.priority)
        for t in sorted_theaters:
            stars = "⭐" * t.priority
            keywords = ", ".join(t.keywords)
            lines.append(f"{stars} *{t.name}*\n   Keywords: _{keywords}_\n")
        
        lines.append(
            f"\n💡 *Commands:*\n"
            f"`/addtheater {movie_id} <name>`\n"
            f"`/removetheater {movie_id} <name>`"
        )
        
        await self.send_reply('\n'.join(lines))
    
    async def cmd_add_theater(self, args: str) -> None:
        """Add theater to a movie"""
        if not args or len(args.split(maxsplit=1)) < 2:
            await self.send_reply(
                "❌ *Usage:* `/addtheater <movie_id> <theater_name>`\n\n"
                "*Example:*\n"
                "`/addtheater leo_chennai SPI Cinemas`"
            )
            return
        
        parts = args.split(maxsplit=1)
        movie_id = parts[0].strip().lower()
        theater_name = parts[1].strip()
        
        movie = self.config.get_movie(movie_id)
        if not movie:
            await self.send_reply(f"❌ Movie not found: `{movie_id}`")
            return
        
        from config import TheaterConfig
        theater = TheaterConfig(
            name=theater_name,
            priority=1,
            keywords=[theater_name.lower()]
        )
        
        if self.config.add_theater_to_movie(movie_id, theater):
            await self.send_reply(
                f"✅ *Theater Added!*\n\n"
                f"🎭 {theater_name}\n"
                f"📽️ Movie: {movie.movie_name}\n\n"
                f"Use `/theaters {movie_id}` to see all theaters"
            )
            logger.info(f"Theater added to {movie_id}: {theater_name}")
        else:
            await self.send_reply(f"❌ Theater already exists or could not be added")
    
    async def cmd_remove_theater(self, args: str) -> None:
        """Remove theater from a movie"""
        if not args or len(args.split(maxsplit=1)) < 2:
            await self.send_reply(
                "❌ *Usage:* `/removetheater <movie_id> <theater_name>`\n\n"
                "*Example:*\n"
                "`/removetheater leo_chennai PVR`"
            )
            return
        
        parts = args.split(maxsplit=1)
        movie_id = parts[0].strip().lower()
        theater_name = parts[1].strip()
        
        movie = self.config.get_movie(movie_id)
        if not movie:
            await self.send_reply(f"❌ Movie not found: `{movie_id}`")
            return
        
        if self.config.remove_theater_from_movie(movie_id, theater_name):
            await self.send_reply(
                f"✅ *Theater Removed!*\n\n"
                f"🎭 {theater_name}\n"
                f"📽️ Movie: {movie.movie_name}"
            )
            logger.info(f"Theater removed from {movie_id}: {theater_name}")
        else:
            await self.send_reply(f"❌ Theater not found: {theater_name}")


class TelegramPoller:
    """Poll Telegram for updates"""
    
    def __init__(self, notifier, command_handler):
        self.notifier = notifier
        self.command_handler = command_handler
        self.last_update_id = 0
        self.session = notifier.session
        self.base_url = notifier.base_url
    
    async def get_updates(self) -> list:
        """Get new updates from Telegram"""
        url = f"{self.base_url}/getUpdates"
        params = {
            "offset": self.last_update_id + 1,
            "timeout": 10,
            "allowed_updates": ["message"]
        }
        
        try:
            async with self.session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('result', [])
        except Exception as e:
            logger.debug(f"Polling error: {e}")
        
        return []
    
    async def process_updates(self) -> None:
        """Process all pending updates"""
        updates = await self.get_updates()
        
        for update in updates:
            update_id = update.get('update_id', 0)
            if update_id > self.last_update_id:
                self.last_update_id = update_id
            
            await self.command_handler.handle_update(update)
