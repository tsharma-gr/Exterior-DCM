from logger_config import logger
from playwright.async_api import Page
import asyncio
import os

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
            
        # Close old tab to free memory before loading next candidate
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass
            self.page = None
            
        if not self.page:
            if not self.playwright:
                logger.warning("No playwright instance provided to CVParser. Falling back to headful page...")
                self.page = await self.context.new_page()
            else:
                if not self.headless_context:
                    logger.info("Initializing background headless browser context for CV parsing...")
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
    
                    headless_env = os.getenv("HEADLESS", "true").lower() == "true"
                    self.headless_browser = await self.playwright.chromium.launch(
                        headless=headless_env,
                        proxy=proxy_config
                    )
                    self.headless_context = await self.headless_browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                
                self.page = await self.headless_context.new_page()
                try:
                    from playwright_stealth import Stealth
                    await Stealth().apply_stealth_async(self.page)
                except Exception as e:
                    logger.error(f"Error applying stealth in background parser: {e}")
            
        logger.info(f"Loading CV in background: {cv_link}")
        
        try:
            # Sync cookies from headful context to headless context to keep recruiter session authenticated
            if self.headless_context:
                cookies = await self.context.cookies()
                await self.headless_context.add_cookies(cookies)

            # Go to the CV page
            await self.page.goto(cv_link, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            
            # 1. Switch to Plain Text or CV tab (Required for best AI reading)
            tab_selectors = [
                "#cv-tabs-plain-text",
                "a#plain-text-tab",
                "text='Plain Text'",
                "a:has-text('Plain Text')",
                # TotalJobs CV Tab Selectors (Must be exact or specific to avoid 'CV Database' header)
                "[data-test-id='cv-tab']",
                "[data-testid='cv-tab']",
                "button:text-is('CV')",
                "a:text-is('CV')",
                "li:text-is('CV')",
                "div[role='tab']:text-is('CV')"
            ]
            
            for selector in tab_selectors:
                try:
                    # Look for elements exactly matching 'CV' or 'Plain Text'
                    tab = self.page.locator(selector).first
                    if await tab.is_visible(timeout=3000):
                        await tab.click(force=True)
                        logger.info(f"Switched to CV/Plain Text view using selector: {selector}")
                        await asyncio.sleep(2)
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
                    
            # 2.5 TotalJobs IFrame / Hidden Overlay extraction
            try:
                for frame in self.page.frames:
                    if frame == self.page.main_frame:
                        continue
                    try:
                        iframe_text = await frame.locator("body").inner_text(timeout=2000)
                        if iframe_text and len(iframe_text.strip()) > 200:
                            if iframe_text.strip() not in text:
                                text += "\n\n--- IFRAME CV CONTENT ---\n\n" + iframe_text
                    except:
                        pass
            except Exception as e:
                logger.error(f"Error during iframe extraction: {e}")
            
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

    async def reveal_contact_details(self):
        """Clicks on any 'View contact details' buttons to unlock/reveal contact details for FIT candidates."""
        if not self.page:
            return False
            
        logger.info("Candidate is FIT. Attempting to reveal contact details...")
        
        selectors = [
            "text='View contact details'",
            "a:has-text('View contact details')",
            "button:has-text('View contact details')",
            "text='View details'",
            "a:has-text('View details')",
            "button:has-text('View details')",
            "text='Unlock'",
            "a:has-text('Unlock')",
            "button:has-text('Unlock')"
        ]
        
        clicked = False
        for selector in selectors:
            try:
                loc = self.page.locator(selector)
                count = await loc.count()
                for i in range(count):
                    btn = loc.nth(i)
                    if await btn.is_visible(timeout=1000):
                        await btn.click(force=True)
                        logger.info(f"Clicked reveal/unlock button using selector: {selector}")
                        clicked = True
                        await asyncio.sleep(4) # Wait for details to load
                        return True
            except Exception as e:
                continue
                
        return clicked

    async def get_contact_details_from_page(self):
        """Extracts email, phone, and linkedin from the page DOM or by re-extracting plain text."""
        info = {"email": None, "phone": None, "linkedin": None}
        if not self.page:
            return info
            
        # 1. Try specific CV-Library profile table cells first (most accurate to avoid header/footer recruiter details)
        try:
            for phone_selector in ["td:text-is('Main Phone') + td", "th:text-is('Main Phone') + td", "td:has-text('Main Phone') + td"]:
                el = self.page.locator(phone_selector).first
                if await el.count() > 0:
                    val = (await el.inner_text()).strip()
                    if val and "view" not in val.lower() and "@" not in val:
                        info["phone"] = val
                        logger.info(f"Extracted phone from Profile cell: {val}")
                        break
        except Exception as e:
            logger.warning(f"Error checking Main Phone cell: {e}")

        try:
            for email_selector in ["td:text-is('Email') + td", "th:text-is('Email') + td", "td:has-text('Email') + td", "td:text-is('Email') + td a"]:
                el = self.page.locator(email_selector).first
                if await el.count() > 0:
                    val = (await el.inner_text()).strip()
                    if val and "view" not in val.lower() and "@" in val:
                        info["email"] = val
                        logger.info(f"Extracted email from Profile cell: {val}")
                        break
        except Exception as e:
            logger.warning(f"Error checking Email cell: {e}")

        # 2. Re-click the Plain Text tab to refresh the plain text view
        try:
            tab_selectors = [
                "#cv-tabs-plain-text",
                "a#plain-text-tab",
                "text='Plain Text'",
                "a:has-text('Plain Text')"
            ]
            for selector in tab_selectors:
                tab = self.page.locator(selector).first
                if await tab.is_visible(timeout=2000):
                    await tab.click(force=True)
                    logger.info("Re-switched to Plain Text tab after unlock.")
                    await asyncio.sleep(2)
                    break
        except Exception as e:
            logger.warning(f"Error re-clicking Plain Text tab: {e}")

        # 3. Re-extract plain text and use regex fallback
        try:
            text = ""
            for selector in ["#cv-text-content", "#cv-text-container", ".cv-plain-text-content", "pre", "div[role='main']", "body"]:
                try:
                    el = self.page.locator(selector).first
                    if await el.count() > 0:
                        text = await el.inner_text()
                        if len(text.strip()) > 800:
                            break
                except:
                    continue
            
            if text:
                import re
                if not info["email"]:
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
                    if email_match:
                        email = email_match.group(0).strip()
                        # Ensure we don't grab cv-library internal support/staff emails
                        if "view" not in email.lower() and "cv-library" not in email.lower() and "cvlibrary" not in email.lower():
                            info["email"] = email
                            logger.info(f"Extracted email from text regex: {email}")
                            
                if not info["phone"]:
                    phone_match = re.search(r'(?:\+44|0)\s*7\d{3}\s*\d{6}|(?:\+44|0)\s*[1239]\d{2,3}\s*\d{5,6}', text)
                    if not phone_match:
                        phone_match = re.search(r'\+?\d{1,4}[-.\s]?\(?\d{1,3}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}', text)
                    if phone_match:
                        phone = phone_match.group(0).strip()
                        if "view" not in phone.lower() and len(phone) > 6:
                            info["phone"] = phone
                            logger.info(f"Extracted phone from text regex: {phone}")

                linkedin_match = re.search(r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+', text)
                if linkedin_match:
                    info["linkedin"] = linkedin_match.group(0).strip()
                    logger.info(f"Extracted LinkedIn from text regex: {info['linkedin']}")
        except Exception as e:
            logger.error(f"Error doing regex fallback for contact info: {e}")
            
        return info

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
