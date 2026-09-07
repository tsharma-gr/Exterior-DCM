import asyncio
import os
import sys
from dotenv import load_dotenv
from browser_manager import BrowserManager
from cv_library_searcher import CVLibrarySearcher
from totaljobs_searcher import TotalJobsSearcher
from cv_parser import CVParser
from ai_classifier import AIClassifier
from supabase_writer import SupabaseWriter
from schedule_manager import get_dcm_schedule
from time_checker import is_within_schedule
import atexit
from processed_tracker import ProcessedTracker
from logger_config import logger

load_dotenv()

# UI Colors
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

def load_booleans():
    try:
        with open("booleans.txt", "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Could not load booleans.txt: {e}")
        return []

BOOLEAN_KEYWORDS_LIST = load_booleans()

async def automation_worker(searcher, tj_searcher, portal_name, cv_parser, ai_mgr, tracker, output_mgr, polling_interval, search_period):
    """The background task that performs the actual search automation logic sequentially."""
    try:
        # ---------------- PRODUCTION / AUTO-START MODE ----------------
        auto_start = os.getenv("AUTO_START", "false").lower() == "true"
        cron_mode = str(os.getenv("CRON_MODE", "false")).strip().lower() == "true"
        search_period_env = os.getenv("SEARCH_PERIOD", "24 hours")
        
        
            
        while True:
            # Only check schedule in local development / interactive mode
            if not cron_mode and not auto_start:
                schedule_name = os.getenv("SCHEDULE_NAME", "Default DCM")
                schedule = await asyncio.to_thread(get_dcm_schedule, schedule_name)
                if schedule is not None and not is_within_schedule(schedule):
                    logger.info(f"{YELLOW}Outside scheduled hours or automation disabled. Sleeping for 5 minutes...{RESET}")
                    await asyncio.sleep(300)
                    continue
                elif schedule is None:
                    logger.info(f"{YELLOW}No schedule configured or Supabase missing. Running without schedule restrictions...{RESET}")

            # 1. CV-Library Loop
            for i, boolean_query in enumerate(BOOLEAN_KEYWORDS_LIST, 1):
                for attempt in range(3):

                    try:

                        logger.info(f"{CYAN}Cycle Started: Running CV-Library Search for Boolean {i}/{len(BOOLEAN_KEYWORDS_LIST)} (Attempt {attempt + 1}/3) ({search_period})...{RESET}")

                        await searcher.run_search_flow(boolean_query, cv_parser, ai_mgr, tracker, output_mgr, search_period)

                        logger.info(f"{GREEN}Finished CV-Library processing for Boolean {i}.{RESET}")

                        break  # Success, exit retry loop

                    except asyncio.CancelledError:

                        raise

                    except Exception as e:

                        logger.error(f"Error in CV-Library search worker cycle for boolean {i} (Attempt {attempt + 1}/3): {e}")

                        if attempt < 2:

                            await asyncio.sleep(5)

                        else:

                            logger.error(f"Max retries reached for CV-Library boolean {i}. Moving to next.")

            # 2. TotalJobs Loop
            for i, boolean_query in enumerate(BOOLEAN_KEYWORDS_LIST, 1):
                for attempt in range(3):

                    try:

                        logger.info(f"{CYAN}Switching to TotalJobs Search for Boolean {i}/{len(BOOLEAN_KEYWORDS_LIST)} (Attempt {attempt + 1}/3) ({search_period})...{RESET}")

                        await tj_searcher.run_search_flow(boolean_query, cv_parser, ai_mgr, tracker, output_mgr, search_period)

                        logger.info(f"{GREEN}Finished TotalJobs processing for Boolean {i}.{RESET}")

                        break  # Success, exit retry loop

                    except asyncio.CancelledError:

                        raise

                    except Exception as e:

                        logger.error(f"Error in TotalJobs search worker cycle for boolean {i} (Attempt {attempt + 1}/3): {e}")

                        if attempt < 2:

                            await asyncio.sleep(5)

                        else:

                            logger.error(f"Max retries reached for TotalJobs boolean {i}. Moving to next.")
            
            logger.info(f"{GREEN}All {len(BOOLEAN_KEYWORDS_LIST)} booleans processed successfully for CV-Library & TotalJobs.{RESET}")
            
            if cron_mode:
                break
                
            logger.info(f"{YELLOW}Cycle completed. Entering Standby Mode for {polling_interval} seconds...{RESET}")
            await asyncio.sleep(polling_interval)
            
    except asyncio.CancelledError:
        logger.info(f"{RED}Automation worker stopped manually.{RESET}")
    except Exception as e:
        logger.critical(f"Worker crashed: {e}")


LOCK_FILE = "automation.lock"

def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)

async def run_automation():
    if os.path.exists(LOCK_FILE):
        logger.error(f"{RED}Lock file '{LOCK_FILE}' exists. Another instance is already running. Exiting immediately to prevent duplicates.{RESET}")
        return
        
    # Create lock file
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
        
    # Ensure lock is removed when script cleanly exits or crashes
    atexit.register(remove_lock)

    # Initialize components
    browser_mgr = BrowserManager()
    tracker = ProcessedTracker()
    ai_mgr = AIClassifier()
    output_mgr = SupabaseWriter()
    
    polling_interval = int(os.getenv("POLLING_INTERVAL_SECONDS", 60))
    
    automation_task = None
    
    try:
        # Start browser and context
        context = await browser_mgr.start()
        if not context:
            logger.error("Could not connect to Chrome. Please ensure you have opened it with the remote-debugging command.")
            return
            
        page = await browser_mgr.get_page()
        criteria_text = {}
        searcher = CVLibrarySearcher(page, context)
        tj_searcher = TotalJobsSearcher(page, context)
        cv_parser = CVParser(context, browser_mgr.playwright)
        
        cron_mode = str(os.getenv("CRON_MODE", "false")).strip().lower() == "true"
        tj_mode = str(os.getenv("TOTALJOBS_MODE", "false")).lower() == "true"
        
        if cron_mode or tj_mode:
            logger.info("Automation worker starting immediately via ENV override...")
            search_period = os.getenv("SEARCH_PERIOD", "24 hours")
            
            if tj_mode:
                class DummySearcher:
                    async def run_search_flow(self, *args, **kwargs): pass
                    async def search_booleans(self, *args, **kwargs): pass
                dummy_cv_searcher = DummySearcher()
                automation_task = asyncio.create_task(
                    automation_worker(dummy_cv_searcher, tj_searcher, "TotalJobs Only", cv_parser, ai_mgr, tracker, output_mgr, polling_interval, search_period)
                )
            else:
                portal_name = "CV-Library & TotalJobs"
                automation_task = asyncio.create_task(
                    automation_worker(searcher, tj_searcher, portal_name, cv_parser, ai_mgr, tracker, output_mgr, polling_interval, search_period)
                )
            await automation_task
            return
        
        
        if str(os.getenv("CRON_MODE", "false")).strip().lower() == "true":
            logger.info("CRON_MODE is enabled. Starting automation worker immediately...")
            run_cv = os.getenv("RUN_CV_LIBRARY", "true").lower() == "true"
            run_tj = os.getenv("RUN_TOTALJOBS", "true").lower() == "true"
            
            if run_cv:
                logger.info("Successfully updated bot status to RUNNING for CV-Library.")
                await automation_worker(searcher, tj_searcher, "CV-Library", cv_parser, ai_mgr, tracker, output_mgr, polling_interval, "24 hours")
            
            if run_tj:
                logger.info("Successfully updated bot status to RUNNING for TotalJobs.")
                await automation_worker(searcher, tj_searcher, "TotalJobs", cv_parser, ai_mgr, tracker, output_mgr, polling_interval, "1 day")
                
            try:
                output_mgr.update_bot_status("COMPLETED")
            except Exception as e:
                logger.error(f"Failed to update bot status: {e}")
            logger.info(f"{GREEN}Cron cycle completed. Shutting down...{RESET}")
            return
            logger.info("Successfully updated bot status to COMPLETED.")
            return
            
        while True:
            # Clear screen or print separator
            print(f"\n{BLUE}{BOLD}" + "═"*60 + f"{RESET}")
            print(f"{BLUE}{BOLD}   TALENTVERSE AI - RECRUITMENT AUTOMATION CONTROL{RESET}")
            print(f"{BLUE}{BOLD}" + "═"*60 + f"{RESET}")
            
            is_running = automation_task and not automation_task.done()
            status_text = f"{GREEN}RUNNING{RESET}" if is_running else f"{RED}STOPPED (Paused){RESET}"
            
            print(f" {BOLD}Status:{RESET} {status_text}")
            # print(f" {BOLD}Profile:{RESET} Default")
            print("-" * 60)
            print(f" [{GREEN}1{RESET}] {BOLD}START / RESUME{RESET} monitoring (CV-Library Search)")
            print(f" [{YELLOW}2{RESET}] {BOLD}STOP / PAUSE{RESET} monitoring")
            print(f" [{CYAN}3{RESET}] {BOLD}START FROM SPECIFIC BOOLEAN{RESET} (1-{len(BOOLEAN_KEYWORDS_LIST)})")
            print(f" [{CYAN}4{RESET}] {BOLD}TEST SPECIFIC CV BY URL{RESET} (Direct bypass)")
            print(f" [{CYAN}5{RESET}] {BOLD}START TOTALJOBS ONLY{RESET} (Skip CV-Library)")
            print(f" [{RED}6{RESET}] {BOLD}EXIT{RESET} (Closes Browser & Program)")
            print("-" * 60)
            
            try:
                choice = await asyncio.to_thread(input, "Select an option (1-6): ")
                choice = choice.strip()
            except (EOFError, KeyboardInterrupt):
                choice = '6'
            
            if choice == '1':
                if is_running:
                    print(f"{YELLOW}(!) Automation is already active.{RESET}")
                else:
                    # Prompt user for search period
                    print(f"\n{CYAN}Select search period (Submitted Since):{RESET}")
                    print(" [1] 24 hours (default)")
                    print(" [2] 3 days")
                    print(" [3] 7 days")
                    print(" [4] 14 days")
                    print(" [5] 28 days")
                    print(" [6] Ever")
                    period_choice = await asyncio.to_thread(input, "Select (1-6) or press enter for default: ")
                    period_choice = period_choice.strip()
                    
                    period_map = {
                        "1": "24 hours",
                        "2": "3 days",
                        "3": "7 days",
                        "4": "14 days",
                        "5": "28 days",
                        "6": "Ever"
                    }
                    search_period = period_map.get(period_choice, os.getenv("SEARCH_PERIOD", "24 hours"))
                    
                    portal_name = "CV-Library & TotalJobs"
                    print(f"{GREEN}(+) Starting search automation worker for {portal_name} with period: {search_period}...{RESET}")
                    automation_task = asyncio.create_task(
                        automation_worker(searcher, tj_searcher, portal_name, cv_parser, ai_mgr, tracker, output_mgr, polling_interval, search_period)
                    )
            
            elif choice == '2':
                if is_running:
                    print(f"{YELLOW}(-) Stopping automation worker...{RESET}")
                    automation_task.cancel()
                    try:
                        # Add a 2-second timeout to prevent the terminal from getting stuck
                        await asyncio.wait_for(automation_task, timeout=2.0)
                    except asyncio.TimeoutError:
                        print(f"{YELLOW}(!) Task stop timed out. Force unbinding...{RESET}")
                    except asyncio.CancelledError:
                        pass
                    print(f"{GREEN}(=) Automation successfully paused.{RESET}")
                else:
                    print(f"{YELLOW}(!) Automation is not running.{RESET}")
            
            elif choice == '3':
                if is_running:
                    print(f"{YELLOW}(!) Automation is already active.{RESET}")
                else:
                    # Prompt user for starting boolean index
                    start_boolean_choice = await asyncio.to_thread(input, f"Enter starting boolean index (1-{len(BOOLEAN_KEYWORDS_LIST)}) to start search from: ")
                    start_boolean_choice = start_boolean_choice.strip()
                    start_boolean_idx = 1
                    if start_boolean_choice.isdigit() and 1 <= int(start_boolean_choice) <= len(BOOLEAN_KEYWORDS_LIST):
                        start_boolean_idx = int(start_boolean_choice)
                    else:
                        print(f"{YELLOW}(!) Invalid index. Defaulting to 1.{RESET}")
                        
                    # Prompt user for search period
                    print(f"\n{CYAN}Select search period (Submitted Since):{RESET}")
                    print(" [1] 24 hours (default)")
                    print(" [2] 3 days")
                    print(" [3] 7 days")
                    print(" [4] 14 days")
                    print(" [5] 28 days")
                    print(" [6] Ever")
                    period_choice = await asyncio.to_thread(input, "Select (1-6) or press enter for default: ")
                    period_choice = period_choice.strip()
                    
                    period_map = {
                        "1": "24 hours",
                        "2": "3 days",
                        "3": "7 days",
                        "4": "14 days",
                        "5": "28 days",
                        "6": "Ever"
                    }
                    search_period = period_map.get(period_choice, os.getenv("SEARCH_PERIOD", "24 hours"))
                    
                    portal_name = "CV-Library & TotalJobs"
                    print(f"{GREEN}(+) Starting search automation worker for {portal_name} with period: {search_period}...{RESET}")
                    automation_task = asyncio.create_task(
                        automation_worker(searcher, tj_searcher, portal_name, cv_parser, ai_mgr, tracker, output_mgr, polling_interval, search_period)
                    )
            
            elif choice == '4':
                try:
                    test_url = await asyncio.to_thread(input, f"{CYAN}Enter Full Candidate URL (CV-Library or TotalJobs): {RESET}")
                    test_url = test_url.replace('\x1b[200~', '').replace('\x1b[201~', '').strip()
                    
                    if "cv-library.co.uk" in test_url or "totaljobs.com" in test_url:
                        # Extract an ID for logging if possible
                        test_id = test_url.split('/')[-1].split('?')[0] if "cv-library" in test_url else "TotalJobs_Test"
                        
                        print(f"{YELLOW}(~) Extracting text from: {test_url}{RESET}")
                        cv_text = await cv_parser.extract_cv_text(test_url)
                        if cv_text:
                            print(f"{YELLOW}(~) Extracted {len(cv_text)} characters. Running AI Classification...{RESET}")
                            ai_result = ai_mgr.classify_candidate(cv_text)
                            
                            print(f"\n{BOLD}--- AI CLASSIFICATION RESULT ---{RESET}")
                            
                            classification = ai_result.get('classification', 'UNKNOWN')
                            if classification.upper() == 'FIT':
                                print(f"{BOLD}Status:{RESET} {GREEN}{classification}{RESET}")
                            else:
                                print(f"{BOLD}Status:{RESET} {RED}{classification}{RESET}")
                                
                            print(f"{BOLD}Detected Role:{RESET} {ai_result.get('current_position', 'N/A')}")
                            print(f"{BOLD}Reasoning:{RESET} {ai_result.get('reasoning', 'N/A')}")
                            print(f"{BOLD}--------------------------------{RESET}\n")
                            
                            email_data = {
                                "name": ai_result.get("candidate_name", "Unknown"),
                                "cv_id": test_id,
                                "cv_link": test_url,
                                "location": ai_result.get("location", "Unknown"),
                                "alert_received_time": "Manual Test",
                                "dcm_type": os.getenv("DCM_TYPE", "Default")
                            }
                            full_data = {**email_data, **ai_result}
                            output_mgr.append_candidate(full_data)
                            print(f"{GREEN}(+) Test candidate {email_data['name']} saved to output.{RESET}")
                            
                        else:
                            print(f"{RED}(!) Failed to extract text. Ensure you are logged into the portal in the browser.{RESET}")
                    else:
                        print(f"{RED}(!) Invalid URL format. Must be a valid CV-Library or TotalJobs link.{RESET}")
                except Exception as e:
                    print(f"{RED}(!) Error during direct test: {e}{RESET}")

            elif choice == '5':
                if is_running:
                    print(f"{YELLOW}(!) Automation is already active.{RESET}")
                else:
                    print(f"\n{CYAN}Select search period for TotalJobs (Submitted Since):{RESET}")
                    print(" [1] 24 hours (default)")
                    print(" [2] 3 days")
                    print(" [3] 7 days")
                    print(" [4] 14 days")
                    print(" [5] 28 days")
                    print(" [6] Ever")
                    period_choice = await asyncio.to_thread(input, "Select (1-6) or press enter for default: ")
                    period_choice = period_choice.strip()
                    
                    period_map = {
                        "1": "24 hours",
                        "2": "3 days",
                        "3": "7 days",
                        "4": "14 days",
                        "5": "28 days",
                        "6": "Ever"
                    }
                    search_period = period_map.get(period_choice, os.getenv("SEARCH_PERIOD", "24 hours"))
                    
                    print(f"{GREEN}(+) Starting search automation worker for TotalJobs ONLY with period: {search_period}...{RESET}")
                    
                    # Create a dummy searcher class that does nothing for CV-Library
                    class DummySearcher:
                        async def run_search_flow(self, *args, **kwargs):
                            pass
                            
                    dummy_cv_searcher = DummySearcher()
                    
                    automation_task = asyncio.create_task(
                        automation_worker(dummy_cv_searcher, tj_searcher, "TotalJobs Only", cv_parser, ai_mgr, tracker, output_mgr, polling_interval, search_period)
                    )

            elif choice == '6':
                print(f"{RED}(!) Exiting and cleaning up...{RESET}")
                if is_running:
                    automation_task.cancel()
                    try:
                        await asyncio.wait_for(automation_task, timeout=2.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
                break
            
            else:
                print(f"{RED}(!) Invalid choice. Please enter 1, 2, 3, 4, 5, or 6.{RESET}")

    except Exception as e:
        logger.critical(f"Critical error in main loop: {e}")
    finally:
        if 'cv_parser' in locals():
            try:
                await cv_parser.close()
            except Exception as e:
                logger.error(f"Error closing cv_parser: {e}")
        await browser_mgr.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        os.system('color')
        
    try:
        asyncio.run(run_automation())
    except KeyboardInterrupt:
        pass
