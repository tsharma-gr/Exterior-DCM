import asyncio
import os
import sys
from dotenv import load_dotenv
from browser_manager import BrowserManager
from logger_config import logger

load_dotenv()

async def test_run():
    logger.info("Initializing components for card dumping...")
    browser_mgr = BrowserManager()
    
    context = await browser_mgr.start()
    if not context:
        logger.error("Could not connect to Chrome.")
        return
        
    page = await browser_mgr.get_page()
    
    logger.info("Navigating to candidate search to inspect cards...")
    await page.goto("https://recruiter.totaljobs.com/CandidateSearchWebMVC/CandidateSearch", wait_until="domcontentloaded")
    await asyncio.sleep(5)
    
    # Wait for cards to be visible
    cards = page.locator("div:has(> div.candidate-identifier-container), div.candidate-card, div.card-row-container, div[role='listitem']")
    count = await cards.count()
    logger.info(f"Found {count} cards on page.")
    
    for i in range(min(5, count)):
        card = cards.nth(i)
        text = await card.inner_text()
        logger.info(f"\n--- Card {i+1} Text Snippet ---")
        logger.info(text[:300] + "...")
        
        # Log some potential name elements and their HTML
        logger.info(f"--- Card {i+1} Potential Name Elements HTML ---")
        for selector in ["h2", "h3", "a.candidate-name", "div.candidate-identifier-container", "a", "span"]:
            loc = card.locator(selector)
            sub_count = await loc.count()
            for j in range(min(3, sub_count)):
                el = loc.nth(j)
                if await el.is_visible():
                    html = await el.evaluate("el => el.outerHTML")
                    logger.info(f"Selector '{selector}' index {j}: {html[:200]}")
                    
    await browser_mgr.close()

if __name__ == "__main__":
    asyncio.run(test_run())
