import os
import asyncio
from logger_config import logger

class SessionManager:
    def __init__(self, page, context):
        self.page = page
        self.context = context
        self.storage_state_path = "storage_state.json"
        
    async def is_logged_in(self):
        """Verify that the recruiter dashboard is accessible and login page is not displayed."""
        try:
            current_url = self.page.url.lower()
            if "login" in current_url or "signin" in current_url:
                return False
                
            email_inputs = await self.page.locator("input[name='email']").count()
            username_inputs = await self.page.locator("input[name='username']").count()
            password_inputs = await self.page.locator("input[type='password']").count()
            
            if email_inputs > 0 or username_inputs > 0 or password_inputs > 0:
                return False
                
            return True
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    async def login_to_cvlibrary(self):
        """Perform automatic login using environment variables."""
        email = os.getenv("CVLIBRARY_EMAIL")
        password = os.getenv("CVLIBRARY_PASSWORD")
        
        if not email or not password:
            logger.error("CVLIBRARY_EMAIL or CVLIBRARY_PASSWORD not found in environment variables!")
            return False
            
        logger.info("Performing automatic login.")
        try:
            await self.page.goto("https://www.cv-library.co.uk/recruiter/login", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # Dismiss cookie banner if present
            cookie_selectors = [
                "#onetrust-accept-btn-handler",
                "button:has-text('Accept')",
                "button:has-text('Agree')",
                "button:has-text('Accept All')"
            ]
            for sel in cookie_selectors:
                try:
                    btn = self.page.locator(sel).first
                    if await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(1)
                        break
                except:
                    pass

            # Fill credentials
            await self.page.fill("input[name='email'], input[name='username'], #email, #emailAddress", email)
            await self.page.fill("input[name='password'], input[name='pass'], input[type='password']", password)
            
            # Click login
            login_btn = self.page.locator("input[type='submit'], button[type='submit'], button:has-text('Login'), button:has-text('Sign In')").first
            await login_btn.click()
            
            # Wait for navigation
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(4)
            
            if await self.is_logged_in():
                logger.info("Login successful.")
                await self.context.storage_state(path=self.storage_state_path)
                logger.info("Session saved.")
                return True
            else:
                logger.error("Login failed! Still on login page or credentials rejected.")
                return False
                
        except Exception as e:
            logger.error(f"Exception during automatic login: {e}")
            return False
