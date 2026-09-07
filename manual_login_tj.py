import asyncio
from browser_manager import BrowserManager
from logger_config import logger

async def manual_login():
    logger.info("Initializing Browser for Manual Interaction...")
    import os
    os.environ["HEADLESS"] = "false"
    browser_mgr = BrowserManager()
    
    try:
        page = await browser_mgr.get_page()
        
        url = "https://recruiter.totaljobs.com/CandidateSearchWebMVC/CandidateSearch"
        logger.info(f"Navigating to {url}")
        
        await page.goto(url)
        
        logger.info("Browser opened. You have 15 minutes to log in and interact manually.")
        logger.info("Close the browser window when you are finished.")
        
        # Wait up to 15 minutes for the user to interact
        # Or until the page is closed manually
        try:
            await page.wait_for_timeout(900_000) # 15 minutes
        except Exception:
            pass
            
    finally:
        logger.info("Closing browser session...")
        await browser_mgr.close()

if __name__ == "__main__":
    asyncio.run(manual_login())
