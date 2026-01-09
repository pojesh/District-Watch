"""
DistrictWatch - Dynamic Movie Booking Monitor
Main application for multi-movie, multi-theatre monitoring
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict

from config import AppConfig, MovieConfig
from browser import BrowserController, CircuitBreaker
from extractor import DataExtractor
from detector import ChangeDetector
from notifier import TelegramNotifier
from state import StateManager
from commands import CommandHandler, TelegramPoller


class MovieMonitor:
    """Monitor a single movie"""
    
    def __init__(self, movie: MovieConfig, shared_components: Dict):
        self.movie = movie
        self.browser = shared_components['browser']
        self.state = shared_components['state']
        self.notifier = shared_components['notifier']
        self.circuit_breaker = shared_components['circuit_breaker']
        self.config = shared_components['config']
        
        # Create extractor with movie's theater config
        self.extractor = DataExtractor(movie.target_theaters)
        self.detector = ChangeDetector(self.state, movie.movie_id)
        
        self.last_check = None
        self.check_count = 0
        self.consecutive_failures = 0
    
    async def check(self) -> bool:
        """Check availability for this movie"""
        self.check_count += 1
        self.last_check = datetime.now()
        
        logger = logging.getLogger(f"monitor.{self.movie.movie_id}")
        logger.info(f"Checking {self.movie.movie_name} (#{self.check_count})")
        
        try:
            # Check circuit breaker
            if not self.circuit_breaker.can_attempt():
                logger.warning("Circuit breaker open, skipping")
                return False
            
            # Fetch page
            page_result = await self.browser.fetch_page_content(self.movie.movie_url)
            
            if not page_result["success"]:
                error = page_result.get("error", "Unknown error")
                logger.error(f"Fetch failed: {error}")
                
                self.circuit_breaker.record_failure()
                self.consecutive_failures += 1
                self.state.record_check(False, 0, f"{self.movie.movie_id}: {error}")
                return False
            
            # Extract data
            extraction_result = self.extractor.process_page_data(page_result)
            
            if not extraction_result["success"]:
                error = extraction_result.get("error", "No data")
                logger.warning(f"Extraction issue: {error}")
                self.state.record_check(True, 0, f"{self.movie.movie_id}: {error}")
                return False
            
            theaters = extraction_result["theaters"]
            logger.info(f"Found {len(theaters)} theaters with availability")
            
            # Record success
            self.circuit_breaker.record_success()
            self.consecutive_failures = 0
            self.state.record_check(True, len(theaters))
            
            # Check for changes and alert
            if theaters:
                should_alert = self.detector.should_alert(theaters)
                
                if should_alert:
                    logger.info("New availability detected! Sending alert...")
                    
                    success = await self.notifier.send_booking_alert(
                        self.movie.movie_name,
                        theaters,
                        self.movie.movie_url
                    )
                    
                    if success:
                        self.state.record_alert(theaters, f"{self.movie.movie_name} alert")
                        logger.info("Alert sent successfully")
                    else:
                        logger.error("Failed to send alert")
                else:
                    logger.debug("No new changes detected")
            
            return True
            
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            self.consecutive_failures += 1
            return False


class DistrictWatch:
    """Multi-movie monitoring orchestrator"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.running = False
        
        # Shared components
        self.state: Optional[StateManager] = None
        self.browser: Optional[BrowserController] = None
        self.notifier: Optional[TelegramNotifier] = None
        self.circuit_breaker: Optional[CircuitBreaker] = None
        
        # Command handling
        self.command_handler: Optional[CommandHandler] = None
        self.telegram_poller: Optional[TelegramPoller] = None
        
        # Movie monitors
        self.monitors: Dict[str, MovieMonitor] = {}
        
        # Setup
        self._setup_logging()
        self._setup_signals()
    
    def _setup_logging(self) -> None:
        """Configure logging"""
        Path(self.config.log_file).parent.mkdir(parents=True, exist_ok=True)
        
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, self.config.log_level))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # File handler
        file_handler = logging.FileHandler(self.config.log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        logging.info("DistrictWatch initialized")
    
    def _setup_signals(self) -> None:
        """Setup signal handlers"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals"""
        logging.info(f"Signal {signum} received, shutting down...")
        self.running = False
    
    async def initialize(self) -> None:
        """Initialize all components"""
        try:
            logging.info("Initializing components...")
            
            # State manager
            self.state = StateManager(self.config.db_path)
            self.state.initialize()
            
            # Browser
            self.browser = BrowserController(self.config)
            await self.browser.initialize()
            
            # Notifier
            self.notifier = TelegramNotifier(self.config)
            await self.notifier.initialize()
            
            # Circuit breaker
            self.circuit_breaker = CircuitBreaker(
                threshold=self.config.circuit_breaker_threshold,
                timeout=self.config.circuit_breaker_timeout
            )
            
            # Command handler
            self.command_handler = CommandHandler(self.config, self.notifier)
            self.telegram_poller = TelegramPoller(self.notifier, self.command_handler)
            
            # Send startup message
            active = self.config.get_active_movies()
            startup_msg = (
                "🎬 *DistrictWatch Started*\n\n"
                f"📽️ Active movies: {len(active)}\n"
                f"🎭 Default theaters: {len(self.config.default_theaters)}\n"
                f"⏱️ Check interval: {self.config.check_interval}s\n\n"
                "📱 Use /help for commands"
            )
            await self.notifier.send_message(startup_msg)
            
            logging.info("All components initialized successfully")
            
        except Exception as e:
            logging.error(f"Initialization failed: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup resources"""
        logging.info("Cleaning up...")
        
        try:
            if self.notifier:
                await asyncio.wait_for(self.notifier.close(), timeout=5)
        except asyncio.TimeoutError:
            logging.warning("Notifier cleanup timed out")
        except Exception as e:
            logging.error(f"Notifier cleanup error: {e}")
        
        try:
            if self.browser:
                await asyncio.wait_for(self.browser.close(), timeout=5)
        except asyncio.TimeoutError:
            logging.warning("Browser cleanup timed out")
        except Exception as e:
            logging.error(f"Browser cleanup error: {e}")
        
        try:
            if self.state:
                self.state.close()
        except Exception as e:
            logging.error(f"State cleanup error: {e}")
    
    def refresh_monitors(self) -> None:
        """Refresh movie monitors based on current config"""
        active_movies = self.config.get_active_movies()
        active_ids = {m.movie_id for m in active_movies}
        
        # Remove monitors for disabled/removed movies
        to_remove = [mid for mid in self.monitors if mid not in active_ids]
        for movie_id in to_remove:
            del self.monitors[movie_id]
            logging.info(f"Removed monitor: {movie_id}")
        
        # Add monitors for new active movies
        shared = {
            'browser': self.browser,
            'state': self.state,
            'notifier': self.notifier,
            'circuit_breaker': self.circuit_breaker,
            'config': self.config
        }
        
        for movie in active_movies:
            if movie.movie_id not in self.monitors:
                self.monitors[movie.movie_id] = MovieMonitor(movie, shared)
                logging.info(f"Added monitor: {movie.movie_id}")
    
    async def check_all_movies(self) -> None:
        """Check all active movies"""
        if not self.monitors:
            logging.debug("No active movies to monitor")
            return
        
        # Run checks concurrently
        tasks = [monitor.check() for monitor in self.monitors.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log summary
        success_count = sum(1 for r in results if r is True)
        logging.info(f"Check complete: {success_count}/{len(results)} successful")
    
    async def run(self) -> None:
        """Main monitoring loop"""
        self.running = True
        check_interval = self.config.check_interval
        command_poll_interval = 3  # Check commands every 3 seconds
        
        last_command_check = 0
        
        logging.info(f"Starting monitoring loop (interval: {check_interval}s)")
        
        while self.running:
            try:
                # Refresh monitors (picks up config changes)
                self.refresh_monitors()
                
                # Check all movies
                if self.monitors:
                    await self.check_all_movies()
                
                # Wait with periodic command checks
                elapsed = 0
                while elapsed < check_interval and self.running:
                    current_time = asyncio.get_event_loop().time()
                    
                    if current_time - last_command_check >= command_poll_interval:
                        try:
                            await self.telegram_poller.process_updates()
                            last_command_check = current_time
                        except Exception as e:
                            logging.error(f"Command polling error: {e}")
                    
                    await asyncio.sleep(min(3, check_interval - elapsed))
                    elapsed += 3
                
            except asyncio.CancelledError:
                logging.info("Monitoring cancelled")
                break
            except Exception as e:
                logging.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(60)
        
        logging.info("Monitoring loop stopped")
    
    async def start(self) -> None:
        """Start the application"""
        try:
            await self.initialize()
            await self.run()
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt")
        except Exception as e:
            logging.error(f"Application error: {e}", exc_info=True)
        finally:
            await self.cleanup()
            logging.info("DistrictWatch stopped")


async def main():
    """Application entry point"""
    try:
        config = AppConfig.from_env()
        config.validate()
        
        app = DistrictWatch(config)
        await app.start()
        
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Startup error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
