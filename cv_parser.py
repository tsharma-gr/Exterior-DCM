from logger_config import logger
from playwright.async_api import Page
import asyncio

class CVParser:
    def __init__(self, browser_context, playwright_instance=None):
        self.context = browser_context # Headful context
        self.playwright = playwright_instance
        self.headless_browser = None
        self.headless_context = None
        self.page = None

    async def extract_cv_text(self, cv_link):
        if not cv_link:
            return None
            
        if not self.page:
            if not self.playwright:
                logger.warning("No playwright instance provided to CVParser. Falling back to headful page...")
                self.page = await self.context.new_page()
            else:
                logger.info("Initializing background headless browser context for CV parsing...")
                self.headless_browser = await self.playwright.chromium.launch(headless=True, channel="chrome")
                self.headless_context = await self.headless_browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
                self.page = await self.headless_context.new_page()
            
        logger.info(f"Loading CV in background: {cv_link}")
        
        try:
            # Sync cookies from headful context to headless context to keep recruiter session authenticated
            if self.headless_context:
                cookies = await self.context.cookies()
                await self.headless_context.add_cookies(cookies)

            # Go to the CV page
            await self.page.goto(cv_link, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            
            # 1. Switch to Plain Text tab (Required for best AI reading)
            tab_selectors = [
                "#cv-tabs-plain-text",
                "a#plain-text-tab",
                "text='Plain Text'",
                "a:has-text('Plain Text')"
            ]
            
            for selector in tab_selectors:
                try:
                    tab = self.page.locator(selector).first
                    if await tab.is_visible(timeout=3000):
                        await tab.click(force=True)
                        logger.info("Switched to Plain Text view.")
                        await asyncio.sleep(1.5)
                        break
                except:
                    continue

            # 2. Extract content using multiple containers
            content_selectors = [
                "#cv-text-content",
                "#cv-text-container",
                ".cv-plain-text-content",
                "pre",
                "div[role='main']",
                "body" # Always fallback to body
            ]
            
            text = ""
            for selector in content_selectors:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0:
                        text = await el.inner_text()
                        if len(text.strip()) > 800:
                            break
                except:
                    continue
            
            final_text = text.strip()
            
            # 3. Validation & Session Error Detection
            if "Login" in final_text[:400] or "register" in final_text[:400]:
                 logger.error("!!! SESSION EXPIRED: Please login manually in the browser.")
                 return None
            
            if len(final_text) < 500:
                logger.error(f"Failed to extract meaningful CV text (found {len(final_text)} chars).")
                return None

            logger.info(f"Successfully extracted {len(final_text)} characters of CV text.")
            return final_text
                
        except Exception as e:
            logger.error(f"Error during CV parsing: {e}")
        
        return None

    async def close(self):
        """Cleans up the background headless browser and pages."""
        try:
            if self.page:
                await self.page.close()
                self.page = None
            if self.headless_context:
                await self.headless_context.close()
                self.headless_context = None
            if self.headless_browser:
                await self.headless_browser.close()
                self.headless_browser = None
            logger.info("CV Parser background browser closed successfully.")
        except Exception as e:
            logger.error(f"Error closing background browser: {e}")
