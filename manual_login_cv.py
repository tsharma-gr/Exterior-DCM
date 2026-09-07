import asyncio
import os
from playwright.async_api import async_playwright
from logger_config import logger

async def run_interactive_login():
    logger.info("Starting interactive login mode for CV-Library...")
    async with async_playwright() as p:
        # Launch visible browser
        browser = await p.chromium.launch(
            headless=False, 
            channel="chrome",
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        
        context_args = {
            "no_viewport": True,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        
        # Load existing session if it exists
        state_path = "storage_state.json"
        if os.path.exists(state_path):
            logger.info(f"Loading existing session from {state_path}...")
            context_args["storage_state"] = state_path
            
        context = await browser.new_context(**context_args)
        page = await context.new_page()
        
        print("\n" + "="*60)
        print(" BROWSER OPENED FOR MANUAL LOGIN ")
        print("="*60)
        print("1. Go to the browser window that just opened.")
        print("2. Log in to CV-Library.")
        print("3. Solve any CAPTCHAs and navigate to the dashboard.")
        print("="*60)
        
        await page.goto("https://www.cv-library.co.uk/client")
        
        try:
            # Wait up to 24 hours
            await page.wait_for_timeout(86_400_000)
        except Exception:
            pass
        finally:
            # Save the session state before closing
            await context.storage_state(path=state_path)
            logger.info(f"Success! Session state saved to {state_path}.")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_interactive_login())
