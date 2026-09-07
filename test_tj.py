import asyncio
import sys
import os
from dotenv import load_dotenv
from browser_manager import BrowserManager
from totaljobs_searcher import TotalJobsSearcher
from cv_parser import CVParser
from ai_classifier import AIClassifier
from supabase_writer import SupabaseWriter
from processed_tracker import ProcessedTracker
from main import BOOLEAN_KEYWORDS
from logger_config import logger

load_dotenv()

async def run_test():
    browser_mgr = BrowserManager()
    tracker = ProcessedTracker()
    ai_mgr = AIClassifier()
    supabase_writer = SupabaseWriter()
    
    try:
        context = await browser_mgr.start()
        if not context:
            logger.error("Could not start browser.")
            return
            
        page = await browser_mgr.get_page()
        tj_searcher = TotalJobsSearcher(page, context)
        cv_parser = CVParser(context, browser_mgr.playwright)
        
        logger.info("Testing TotalJobs integration exclusively...")
        
        # Test with a short period so it doesn't take forever, or 1 day
        search_period = "1 day" 
        await tj_searcher.run_search_flow(BOOLEAN_KEYWORDS, cv_parser, ai_mgr, tracker, supabase_writer, search_period)
        
        logger.info("TotalJobs test complete.")
        
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        if 'cv_parser' in locals():
            try:
                await cv_parser.close()
            except:
                pass
        await browser_mgr.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        os.system('color')
    asyncio.run(run_test())
