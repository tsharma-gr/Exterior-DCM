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
        self.storage_state_path = "storage_state.json"

    async def start(self):
        headless_env = os.getenv("HEADLESS", "true").lower() == "true"
        logger.info(f"Launching Chrome (Headless={headless_env}) with session management.")
        self.playwright = await async_playwright().start()
        
        try:
            storage_state = self.storage_state_path if os.path.exists(self.storage_state_path) else None
            if storage_state:
                logger.info("Loaded existing session.")
            else:
                logger.info("No existing session found. Will require login.")

            self.browser = await self.playwright.chromium.launch(
                headless=headless_env,
                args=[
                    "--start-maximized",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars"
                ]
            )
            
            self.context = await self.browser.new_context(
                storage_state=storage_state,
                no_viewport=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
            
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
            from playwright_stealth import stealth
            await stealth(page)
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
        
        pages = self.context.pages
        if pages:
            return pages[0]
        return await self.context.new_page()

    async def close(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("Browser closed.")
