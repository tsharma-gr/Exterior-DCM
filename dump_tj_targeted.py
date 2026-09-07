import asyncio
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv

load_dotenv()

async def dump_targeted():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        print("Navigating to TotalJobs...")
        await page.goto("https://recruiter.totaljobs.com/CandidateSearchWebMVC/CandidateSearch", wait_until="domcontentloaded")
        
        # Login
        email = os.getenv("TOTALJOBS_EMAIL")
        pwd = os.getenv("TOTALJOBS_PASSWORD")
        if email and pwd:
            try:
                print("Logging in...")
                await page.locator("input[type='email']").first.fill(email)
                await page.locator("input[type='password']").fill(pwd)
                await page.locator("button:has-text('Sign in'), button[type='submit']").first.click()
                await page.wait_for_load_state("domcontentloaded")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Login failed: {e}")
        
        print("Clicking Targeted tab...")
        try:
            targeted_tab = page.locator("a:text-is('Targeted'), [role='tab']:text-is('Targeted'), li:not(.active):has-text('Targeted')").first
            await targeted_tab.click()
            await asyncio.sleep(4)
        except Exception as e:
            print(f"Could not click Targeted tab: {e}")
            
        print("Dumping HTML...")
        html = await page.content()
        with open("targeted_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("Done!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(dump_targeted())
