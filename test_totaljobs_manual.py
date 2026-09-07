import asyncio
import os
import sys
from dotenv import load_dotenv
from browser_manager import BrowserManager
from totaljobs_searcher import TotalJobsSearcher
from cv_parser import CVParser
from ai_classifier import AIClassifier
from supabase_writer import SupabaseWriter
from processed_tracker import ProcessedTracker
from logger_config import logger

# Import main to inspect variables dynamically
import main

load_dotenv()

# We override CRON_MODE environment variable so that the TotalJobs search bypass is not active
os.environ["CRON_MODE"] = "false"

async def test_run():
    logger.info("Initializing components for TotalJobs testing...")
    browser_mgr = BrowserManager()
    tracker = ProcessedTracker()
    ai_mgr = AIClassifier()
    supabase_writer = SupabaseWriter()
    
    context = await browser_mgr.start()
    if not context:
        logger.error("Could not connect to Chrome.")
        return
        
    page = await browser_mgr.get_page()
    tj_searcher = TotalJobsSearcher(page, context)
    cv_parser = CVParser(context, browser_mgr.playwright)
    
    # Dynamically extract booleans
    booleans = []
    if hasattr(main, "BOOLEAN_KEYWORDS_LIST"):
        booleans = getattr(main, "BOOLEAN_KEYWORDS_LIST")
        logger.info("Detected BOOLEAN_KEYWORDS_LIST in main.py")
    elif hasattr(main, "BOOLEAN_KEYWORDS"):
        booleans.append(getattr(main, "BOOLEAN_KEYWORDS"))
        if hasattr(main, "BOOLEAN_KEYWORDS_2"):
            booleans.append(getattr(main, "BOOLEAN_KEYWORDS_2"))
        logger.info("Detected BOOLEAN_KEYWORDS / BOOLEAN_KEYWORDS_2 in main.py")
    else:
        logger.error("Could not find any search booleans in main.py!")
        return
        
    for idx, q in enumerate(booleans, 1):
        logger.info(f"Starting TotalJobs search flow for Boolean {idx}/{len(booleans)}...")
        logger.info(f"Query: {q[:120]}...")
        await tj_searcher.run_search_flow(q, cv_parser, ai_mgr, tracker, supabase_writer, search_period="24 hours")
    
    logger.info("Manual testing finished. Cleaning up...")
    await cv_parser.close()
    await browser_mgr.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        os.system('color')
    asyncio.run(test_run())
