import asyncio
import os
import sys
from dotenv import load_dotenv
from browser_manager import BrowserManager
from cv_library_searcher import CVLibrarySearcher
from cv_parser import CVParser
from ai_classifier import AIClassifier
from supabase_writer import SupabaseWriter
from processed_tracker import ProcessedTracker
from logger_config import logger
from schedule_manager import get_dcm_schedule
from time_checker import is_within_schedule

load_dotenv()

# UI Colors
GREEN = "\033[92m"
RED = "\033[91m"
BLUE = "\033[94m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

BOOLEAN_KEYWORDS = (
    '("Curtain walling" OR Rainscreen OR "Building Envelope" OR "Curtain wall" OR Facade OR Glazing OR kawneer OR scheuco OR schuco OR "Structural glass" OR "architectural glazing" OR "unitized curtain wall" OR "exterior envelope" OR "industrial roofing" OR "single ply" OR "membrane roofing" OR "flat roofing" OR "standing seam" OR "metal roofing" OR "Industrial roof" OR "Flat roof" OR Cladding OR Roofing) '
    'AND (Design OR CAD OR Designer OR Draughtsmen OR draughtsman OR Estimator OR "Estimating Manager" OR "Estimating Director" OR "Pre Construction Director" OR "Pre-Construction Director" OR "Design Manager" OR "Design Director" OR "Drawing Office" OR Bid OR Bidding OR "Bidding Manager" OR "Bidding Director" OR QS OR "Quantity Surveyor" OR "Commercial Manager" OR "Commercial Director" OR Planner OR Buyer OR sales OR "business development" OR "BDM" OR "Project Manager" OR "Site Manager" OR "Contract Manager" OR "Contracts Manager" OR "Delivery Manager" OR "Project Director" OR "Site Director" OR "Contract Director" OR "Contracts Director" OR "Delivery Director" OR "Site Supervisor")'
)

async def automation_worker(searcher, cv_parser, ai_mgr, tracker, supabase_writer, polling_interval, search_period):
    """The background task that performs the actual CV-Library search automation logic."""
    try:
        while True:
            try:
                # Read Schedule -> Check Time -> Process or Sleep
                schedule = await asyncio.to_thread(get_dcm_schedule, "Exterior DCM")
                
                if not schedule or not is_within_schedule(schedule):
                    logger.info(f"{YELLOW}Outside scheduled hours or automation disabled. Sleeping for 5 minutes...{RESET}")
                    await asyncio.sleep(300)
                    continue

                logger.info(f"{CYAN}Cycle Started: Running CV-Library Search ({search_period})...{RESET}")
                
                # Run direct search flow
                work_done = await searcher.run_search_flow(BOOLEAN_KEYWORDS, cv_parser, ai_mgr, tracker, supabase_writer, search_period)
                
                if work_done:
                    logger.info(f"{GREEN}Search and processing completed. Checking again in 10 seconds...{RESET}")
                    await asyncio.sleep(10)
                    continue
                
                logger.info(f"{YELLOW}No new unprocessed candidates found. Entering Standby Mode...{RESET}")
                await asyncio.sleep(polling_interval)
                
            except asyncio.CancelledError:
                raise # Propagate to outer catch
            except Exception as e:
                logger.error(f"Error in search worker cycle: {e}")
                await asyncio.sleep(30)
    except asyncio.CancelledError:
        logger.info(f"{RED}Automation worker stopped.{RESET}")
    except Exception as e:
        logger.critical(f"Worker crashed: {e}")

async def run_automation():
    # Initialize components
    browser_mgr = BrowserManager()
    tracker = ProcessedTracker()
    ai_mgr = AIClassifier()
    supabase_writer = SupabaseWriter()
    
    polling_interval = int(os.getenv("POLLING_INTERVAL_SECONDS", 60))
    
    automation_task = None
    
    try:
        # Start browser and context
        context = await browser_mgr.start()
        if not context:
            logger.error("Could not connect to Chrome. Please ensure you have opened it with the remote-debugging command.")
            return
            
        page = await browser_mgr.get_page()
        searcher = CVLibrarySearcher(page, context)
        cv_parser = CVParser(context, browser_mgr.playwright)
        
        # ---------------- PRODUCTION / AUTO-START MODE ----------------
        auto_start = os.getenv("AUTO_START", "false").lower() == "true"
        search_period = os.getenv("SEARCH_PERIOD", "24 hours")
        
        if auto_start:
            logger.info(f"{GREEN}AUTO_START=true detected. Starting production mode without terminal UI.{RESET}")
            # Await the worker directly so it runs indefinitely
            await automation_worker(
                searcher, cv_parser, ai_mgr, tracker, supabase_writer, polling_interval, search_period
            )
            return
            
        # ---------------- LOCAL DEVELOPMENT / INTERACTIVE MODE ----------------
        while True:
            # Clear screen or print separator
            print(f"\n{BLUE}{BOLD}" + "═"*60 + f"{RESET}")
            print(f"{BLUE}{BOLD}   TALENTVERSE AI - RECRUITMENT AUTOMATION CONTROL{RESET}")
            print(f"{BLUE}{BOLD}" + "═"*60 + f"{RESET}")
            
            is_running = automation_task and not automation_task.done()
            status_text = f"{GREEN}RUNNING{RESET}" if is_running else f"{RED}STOPPED (Paused){RESET}"
            
            print(f" {BOLD}Status:{RESET} {status_text}")
            print(f" {BOLD}Profile:{RESET} {browser_mgr.user_data_dir}")
            print("-" * 60)
            print(f" [{GREEN}1{RESET}] {BOLD}START / RESUME{RESET} monitoring (CV-Library Search)")
            print(f" [{YELLOW}2{RESET}] {BOLD}STOP / PAUSE{RESET} monitoring")
            print(f" [{CYAN}3{RESET}] {BOLD}OPEN CV-LIBRARY SEARCH PAGE{RESET} (Manual navigation)")
            print(f" [{CYAN}4{RESET}] {BOLD}TEST SPECIFIC CV BY ID{RESET} (Direct CV-Library bypass)")
            print(f" [{RED}5{RESET}] {BOLD}EXIT{RESET} (Closes Browser & Program)")
            print("-" * 60)
            
            try:
                choice = await asyncio.to_thread(input, "Select an option (1-5): ")
                choice = choice.strip()
            except (EOFError, KeyboardInterrupt):
                choice = '5'
            
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
                    
                    print(f"{GREEN}(+) Starting search automation worker with period: {search_period}...{RESET}")
                    automation_task = asyncio.create_task(
                        automation_worker(searcher, cv_parser, ai_mgr, tracker, supabase_writer, polling_interval, search_period)
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
                print(f"{CYAN}(>) Navigating to CV-Library Candidate Search...{RESET}")
                await page.goto("https://www.cv-library.co.uk/recruiter/candidate-search", wait_until="domcontentloaded")
            
            elif choice == '4':
                try:
                    test_id = await asyncio.to_thread(input, f"{CYAN}Enter CV ID (e.g. 30769000): {RESET}")
                    test_id = test_id.strip().replace("CV:", "").strip()
                    if test_id.isdigit():
                        test_url = f"https://www.cv-library.co.uk/recruiter/cv/{test_id}"
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
                                "platform_name": "Manual Test"
                            }
                            full_data = {**email_data, **ai_result}
                            supabase_writer.append_candidate(full_data)
                            print(f"{GREEN}(+) Test candidate {email_data['name']} saved to output.{RESET}")
                            
                        else:
                            print(f"{RED}(!) Failed to extract text. Ensure you are logged into CV-Library in the browser.{RESET}")
                    else:
                        print(f"{RED}(!) Invalid CV ID format. Must be numbers only.{RESET}")
                except Exception as e:
                    print(f"{RED}(!) Error during direct test: {e}{RESET}")

            elif choice == '5':
                print(f"{RED}(!) Exiting and cleaning up...{RESET}")
                if is_running:
                    automation_task.cancel()
                    try:
                        await asyncio.wait_for(automation_task, timeout=2.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        pass
                break
            
            else:
                print(f"{RED}(!) Invalid choice. Please enter 1, 2, 3, 4, or 5.{RESET}")

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
