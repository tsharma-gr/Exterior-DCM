import os
import asyncio
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from logger_config import logger

load_dotenv()

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.context = None
        self.browser = None
        self.is_remote = False
        self.storage_state_path = "storage_state.json"

    async def start(self):
        headless_env = os.getenv("HEADLESS", "true").lower() == "true"
        logger.info(f"Launching Chrome (Headless={headless_env}) with session management.")
        self.playwright = await async_playwright().start()
        
        try:
            try:
                # Try to connect to an existing manual Chrome browser first
                cdp_port = os.getenv("CDP_PORT", "9223")
                self.is_remote = True
                self.browser = await self.playwright.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
                self.context = self.browser.contexts[0]
                logger.info(f"Successfully connected to existing manual Chrome browser on port {cdp_port}.")
                
                # Setup download handlers
                self.context.on("page", lambda p: asyncio.create_task(self._setup_page(p)))
                for p in self.context.pages:
                    await self._setup_page(p)
                return self.context
            except Exception:
                logger.info("No existing browser found on port 9223. Launching headless fallback.")

            proxy_server = os.getenv("PROXY_SERVER")
            proxy_username = os.getenv("PROXY_USERNAME")
            proxy_password = os.getenv("PROXY_PASSWORD")
            
            proxy_config = None
            if proxy_server:
                proxy_config = {
                    "server": proxy_server,
                }
                if proxy_username and proxy_password:
                    proxy_config["username"] = proxy_username
                    proxy_config["password"] = proxy_password

            # Use standard launch instead of persistent context or CDP
            self.browser = await self.playwright.chromium.launch(
                headless=headless_env,
                channel="chrome" if not headless_env else None, # Use default chromium in headless/VPS
                proxy=proxy_config,
                ignore_default_args=["--enable-automation"],
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars"
                ]
            )

            context_args = {
                "no_viewport": True,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            
            if os.path.exists(self.storage_state_path):
                context_args["storage_state"] = self.storage_state_path

            self.context = await self.browser.new_context(**context_args)
            
            # Prevent the site from instantly closing the tab, which was cancelling the downloads
            await self.context.add_init_script("""
                const originalClose = window.close;
                window.close = function() {
                    console.log('Close blocked to allow download to finish');
                    setTimeout(() => { originalClose.call(window); }, 3000);
                };
            """)
            
            # Setup download handlers and stealth for all pages
            self.context.on("page", lambda p: asyncio.create_task(self._setup_page(p)))
            for p in self.context.pages:
                await self._setup_page(p)
                
            logger.info("Successfully launched stealth browser.")
            return self.context
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            return None

    async def _setup_page(self, page):
        try:
            from playwright_stealth import Stealth
            await Stealth().apply_stealth_async(page)
        except Exception as e:
            logger.error(f"Error applying stealth: {e}")
        page.on("download", self._handle_download)

    async def _handle_download(self, download):
        import os
        import re
        try:
            downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
            
            # Sanitize the filename to prevent Windows OS errors from special characters
            safe_filename = re.sub(r'[\\/*?:"<>|]', "", download.suggested_filename)
            final_path = os.path.join(downloads_dir, safe_filename)
            
            # Wait for download to finish and securely copy it from TEMP to Downloads
            await download.save_as(final_path)
            
            logger.info(f"Successfully recovered and renamed download to: {download.suggested_filename}")
        except Exception as e:
            logger.error(f"Failed to save manual download: {e}")

    async def get_page(self):
        if not self.context:
            await self.start()
            
        # ALWAYS create a new tab for each bot session to prevent simultaneous bots from fighting over the same tab
        self.active_page = await self.context.new_page()
        return self.active_page

    async def close(self):
        if hasattr(self, 'active_page') and self.active_page:
            try:
                await self.active_page.close()
            except Exception:
                pass
        if self.context:
            try:
                if not getattr(self, 'is_remote', False):
                    await self.context.close()
            except Exception:
                pass
        if self.browser:
            try:
                if not getattr(self, 'is_remote', False):
                    await self.browser.close()
            except Exception:
                pass
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed.")
