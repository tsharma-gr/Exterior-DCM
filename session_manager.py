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
            
            # Check for login/signin FIRST, because the redirect parameter might contain 'candidate-search'
            if "login" in current_url or "signin" in current_url:
                return False
                
            if "candidate-search" in current_url or "/recruiter/cv" in current_url or "dashboard" in current_url:
                title = await self.page.title()
                if "Just a moment" in title or "Blocked" in title:
                    logger.warning("Cloudflare/WAF protection detected. Session invalid.")
                    return False
                return True
                
            # Only check for login fields if we aren't clearly on a logged-in page
            password_inputs = await self.page.locator("input[type='password']").count()
            if password_inputs > 0:
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

            # Fill credentials (updated selectors for CV-Library)
            email_locator = self.page.locator("input[type='email'], input[name='email'], input[name='client_email'], input[name='username'], #email").first
            await email_locator.fill(email)
            
            pass_locator = self.page.locator("input[type='password']").first
            await pass_locator.fill(password)
            
            # Click login
            login_btn = self.page.locator("button:has-text('Login'), input[type='submit'], input[value*='Login']").first
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

    async def login_to_totaljobs(self):
        """Perform automatic login for TotalJobs using environment variables."""
        email = os.getenv("TOTALJOBS_EMAIL")
        password = os.getenv("TOTALJOBS_PASSWORD")
        
        if not email or not password:
            logger.error("TOTALJOBS_EMAIL or TOTALJOBS_PASSWORD not found in environment variables!")
            return False
            
        logger.info("Performing automatic login for TotalJobs.")
        try:
            await self.page.goto("https://recruiter.totaljobs.com/Login", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # Dismiss cookie banner if present
            cookie_selectors = [
                "#ccm-accept-all-btn",
                "#onetrust-accept-btn-handler",
                "button:has-text('Accept All')",
                "button:has-text('Accept cookies')",
                "button:has-text('Accept')"
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
            email_locator = self.page.locator("input[type='email'], input[name='Email'], input[name='email'], input#Email, input[name*='username' i], input[name*='email' i]").first
            await email_locator.fill(email)
            
            pass_locator = self.page.locator("input[type='password'], input[name='Password'], input[name='password'], input#Password, input[name*='password' i]").first
            await pass_locator.fill(password)
            
            # Click login
            login_btn = self.page.locator("button:has-text('Sign in'), input[value='Sign in'], button:has-text('Log in'), button:has-text('Login'), input[type='submit'], button[type='submit']").first
            await login_btn.click()
            
            # Wait for navigation
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(4)
            
            if await self.is_logged_in():
                logger.info("TotalJobs Login successful.")
                await self.context.storage_state(path=self.storage_state_path)
                logger.info("Session saved.")
                return True
            else:
                logger.error("TotalJobs Login failed! Checking if it is an Email Verification block...")
                current_url = self.page.url.lower()
                
                if "verify" in current_url or "verification" in current_url or "safelistloginblocked" in current_url:
                    logger.warning("Email Verification Block Detected!")
                    try:
                        from discord_alert import pause_and_alert_email_verify
                        await pause_and_alert_email_verify(self.page)
                        
                        if await self.is_logged_in():
                            logger.info("TotalJobs Login successful after manual verification!")
                            await self.context.storage_state(path=self.storage_state_path)
                            logger.info("Session saved.")
                            return True
                    except Exception as verify_e:
                        logger.error(f"Error during verification pause loop: {verify_e}")
                        
                logger.error("TotalJobs Login failed! Still on login page or credentials rejected.")
                return False
                
        except Exception as e:
            logger.error(f"Exception during TotalJobs automatic login: {e}")
            return False
