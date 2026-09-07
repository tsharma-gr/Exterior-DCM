import asyncio
import os
import sys
from dotenv import load_dotenv
from browser_manager import BrowserManager
from totaljobs_searcher import TotalJobsSearcher
from logger_config import logger

load_dotenv()

async def test_run():
    logger.info("Initializing components for dumping candidate names...")
    browser_mgr = BrowserManager()
    
    context = await browser_mgr.start()
    if not context:
        logger.error("Could not connect to Chrome.")
        return
        
    page = await browser_mgr.get_page()
    tj_searcher = TotalJobsSearcher(page, context)
    
    # We navigate and run the search first to load the candidate cards
    logger.info("Navigating to candidate search...")
    await tj_searcher.navigate_to_search(use_boolean_tab=True)
    
    # Fill boolean
    logger.info("Filling keywords...")
    await tj_searcher.robust_fill(["#txtBooleanMvc"], '("Curtain walling" OR Facade OR Cladding) AND Design')
    await tj_searcher.robust_fill(["input#Location"], "UK")
    await asyncio.sleep(1)
    await page.keyboard.press("Enter")
    
    # Click search
    logger.info("Submitting search...")
    await page.locator("input[value='Search']").first.click()
    await asyncio.sleep(8)
    
    # Locate candidate identifier containers
    containers = page.locator("div.candidate-identifier-container")
    count = await containers.count()
    logger.info(f"Found {count} candidate-identifier-containers.")
    
    for i in range(count):
        html = await containers.nth(i).evaluate("el => el.outerHTML")
        text = await containers.nth(i).inner_text()
        logger.info(f"Container {i+1} HTML: {html[:300]}")
        logger.info(f"Container {i+1} Inner Text: {text}")
        
    await browser_mgr.close()

if __name__ == "__main__":
    asyncio.run(test_run())
