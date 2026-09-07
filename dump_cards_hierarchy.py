import asyncio
import os
import sys
from dotenv import load_dotenv
from browser_manager import BrowserManager
from totaljobs_searcher import TotalJobsSearcher
from logger_config import logger

load_dotenv()

async def test_run():
    logger.info("Initializing components...")
    browser_mgr = BrowserManager()
    
    context = await browser_mgr.start()
    if not context:
        logger.error("Could not connect to Chrome.")
        return
        
    page = await browser_mgr.get_page()
    tj_searcher = TotalJobsSearcher(page, context)
    
    logger.info("Navigating to search page...")
    await tj_searcher.navigate_to_search(use_boolean_tab=True)
    
    # Fill boolean
    logger.info("Filling keywords...")
    await tj_searcher.robust_fill(["#txtBooleanMvc"], '("Curtain walling" OR Facade OR Cladding) AND Design')
    await tj_searcher.robust_fill(["input#Location"], "UK")
    await asyncio.sleep(1)
    await page.keyboard.press("Enter")
    
    logger.info("Submitting search...")
    await page.locator("input[value='Search']").first.click()
    await asyncio.sleep(8)
    
    # Find the first identifier container
    identifier = page.locator("div.candidate-identifier-container").first
    if await identifier.count() > 0:
        logger.info("Found candidate-identifier-container. Let's dump its hierarchy.")
        
        # Traverse up and log tags, classes, and inner text lengths
        current = identifier
        for level in range(1, 6):
            parent = current.locator("xpath=..")
            if await parent.count() > 0:
                tag = await parent.evaluate("el => el.tagName")
                class_name = await parent.get_attribute("class") or ""
                text_len = len(await parent.inner_text() or "")
                text_preview = (await parent.inner_text() or "")[:150].replace("\n", " ")
                logger.info(f"Ancestor Level {level}: Tag={tag}, Class='{class_name}', Text Length={text_len}, Preview='{text_preview}'")
                
                # Check what children this parent has
                children_count = await parent.locator("xpath=child::*").count()
                logger.info(f"  Children count: {children_count}")
                for c_idx in range(min(5, children_count)):
                    c_el = parent.locator("xpath=child::*").nth(c_idx)
                    c_tag = await c_el.evaluate("el => el.tagName")
                    c_class = await c_el.get_attribute("class") or ""
                    logger.info(f"    Child {c_idx+1}: Tag={c_tag}, Class='{c_class}'")
                    
                current = parent
            else:
                logger.info("No more parent elements.")
                break
                
    await browser_mgr.close()

if __name__ == "__main__":
    asyncio.run(test_run())
