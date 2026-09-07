import asyncio
from playwright.async_api import async_playwright

async def dump_targeted_9222():
    async with async_playwright() as p:
        try:
            print("Connecting to Chrome on 9222...")
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            contexts = browser.contexts
            if not contexts:
                print("No contexts found")
                return
            context = contexts[0]
            pages = context.pages
            if not pages:
                print("No pages found")
                return
            page = pages[0]
            
            print("Navigating to TotalJobs Targeted...")
            await page.goto("https://recruiter.totaljobs.com/CandidateSearchWebMVC/CandidateSearch", wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            print("Clicking Targeted tab...")
            try:
                targeted_tab = page.locator("a:text-is('Targeted'), [role='tab']:text-is('Targeted'), li:not(.active):has-text('Targeted')").first
                await targeted_tab.click()
                await asyncio.sleep(4)
            except Exception as e:
                print(f"Could not click Targeted tab: {e}")
                
            print("Dumping HTML...")
            html = await page.content()
            with open("targeted_dump_9222.html", "w", encoding="utf-8") as f:
                f.write(html)
            print("Done!")
        except Exception as e:
            print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(dump_targeted_9222())
