import asyncio
import os
from playwright.async_api import async_playwright
from logger_config import logger

async def run_interactive_login():
    logger.info("Starting interactive login mode...")
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
        
        # Load existing session if it exists (so you don't lose CV-Library login)
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
        print("2. Paste your TotalJobs verification link.")
        print("3. Complete the login process until you see the normal dashboard.")
        print("4. (Optional) You can also check if CV-Library is still logged in.")
        print("="*60)
        
        # Go to TotalJobs initially to make it easy
        await page.goto("https://recruiter.totaljobs.com/")
        
        # Wait for user input in terminal
        input("\n>>> Press ENTER here in the terminal ONLY AFTER you have fully logged in... <<<")
        
        # Save the combined session state
        await context.storage_state(path=state_path)
        logger.info(f"Success! Session state saved to {state_path}.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_interactive_login())
