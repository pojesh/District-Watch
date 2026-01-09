"""
Browser automation with anti-detection measures
"""

import asyncio
import logging
from typing import Optional, Dict
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class BrowserController:
    """Manages Playwright browser with stealth mode"""
    
    def __init__(self, config):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._playwright = None
    
    async def initialize(self) -> None:
        """Initialize browser instance"""
        try:
            self._playwright = await async_playwright().start()
            
            # Launch with anti-detection
            self.browser = await self._playwright.chromium.launch(
                headless=self.config.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process"
                ]
            )
            
            # Create stealth context
            self.context = await self.browser.new_context(
                user_agent=self.config.user_agent,
                viewport={"width": 1920, "height": 1080},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                permissions=["geolocation"],
                geolocation={"latitude": 13.0827, "longitude": 80.2707},
                extra_http_headers={
                    "Accept-Language": "en-IN,en;q=0.9",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
                }
            )
            
            # Add stealth scripts
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en', 'hi'] });
            """)
            
            logger.info("Browser initialized")
            
        except Exception as e:
            logger.error(f"Browser initialization failed: {e}")
            raise
    
    async def close(self) -> None:
        """Clean up browser resources"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("Browser closed")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    @asynccontextmanager
    async def get_page(self):
        """Context manager for page instances"""
        page = None
        try:
            page = await self.context.new_page()
            page.set_default_timeout(self.config.request_timeout)
            yield page
        finally:
            if page:
                await page.close()
    
    async def fetch_page_content(self, url: str, wait_for_selector: Optional[str] = None) -> Dict:
        """Fetch page content with error handling"""
        result = {
            "success": False,
            "content": None,
            "html": None,
            "error": None,
            "status_code": None
        }
        
        async with self.get_page() as page:
            try:
                logger.debug(f"Fetching: {url}")
                
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.config.request_timeout
                )
                
                result["status_code"] = response.status if response else None
                
                if response and response.status == 403:
                    result["error"] = "Access denied (403) - possible IP block"
                    logger.warning(result["error"])
                    return result
                
                # Wait for dynamic content
                await asyncio.sleep(2)
                
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=10000)
                    except:
                        pass
                
                # Extract __NEXT_DATA__
                next_data = await page.evaluate("""
                    () => {
                        const script = document.querySelector('#__NEXT_DATA__');
                        return script ? script.textContent : null;
                    }
                """)
                
                html = await page.content()
                
                result["success"] = True
                result["content"] = next_data
                result["html"] = html
                
                logger.debug(f"Fetched successfully (status: {result['status_code']})")
                
            except asyncio.TimeoutError:
                result["error"] = "Page load timeout"
                logger.error(result["error"])
            except Exception as e:
                result["error"] = str(e)
                logger.error(f"Fetch error: {e}")
        
        return result


class CircuitBreaker:
    """Circuit breaker to prevent cascading failures"""
    
    def __init__(self, threshold: int = 5, timeout: int = 300):
        self.threshold = threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"
    
    def record_success(self) -> None:
        """Reset on success"""
        self.failures = 0
        self.state = "CLOSED"
    
    def record_failure(self) -> None:
        """Record failure"""
        self.failures += 1
        self.last_failure_time = asyncio.get_event_loop().time()
        
        if self.failures >= self.threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker OPEN after {self.failures} failures")
    
    def can_attempt(self) -> bool:
        """Check if request should be attempted"""
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            current_time = asyncio.get_event_loop().time()
            if current_time - self.last_failure_time >= self.timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker HALF_OPEN")
                return True
            return False
        
        return True  # HALF_OPEN
    
    def get_state(self) -> str:
        return self.state
