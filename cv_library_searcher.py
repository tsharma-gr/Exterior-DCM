import asyncio
import re
import os
from logger_config import logger
from playwright.async_api import Page
from session_manager import SessionManager

class CVLibrarySearcher:
    def __init__(self, page: Page, context):
        self.page = page
        self.context = context
        self.search_url = "https://www.cv-library.co.uk/recruiter/candidate-search"
        self.session_manager = SessionManager(page, context)

    async def run_search_flow(self, boolean_keywords, cv_parser, ai_mgr, tracker, criteria_text, supabase_writer, search_period="24 hours"):
        """Performs search on CV-Library and processes all matching CVs."""
        current_url = self.page.url
        if "submit_cv_search" in current_url or "enc_keywords" in current_url:
            logger.info("Detected active search results page. Resuming processing from current view...")
            work_done = await self.process_all_search_pages(cv_parser, ai_mgr, tracker, criteria_text, supabase_writer)
            return work_done

        logger.info("Navigating to CV-Library Candidate Search...")
        await self.page.goto(self.search_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # Try to dismiss cookie/consent dialog if it appears
        cookie_selectors = [
            "#onetrust-accept-btn-handler",
            "button:has-text('Accept')",
            "button:has-text('Agree')",
            "button:has-text('Accept All')",
            "#agree-button",
            "text='Accept Cookies'"
        ]
        for sel in cookie_selectors:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible():
                    await btn.click()
                    logger.info("Dismissed cookie consent banner.")
                    await asyncio.sleep(1)
                    break
            except:
                pass

        # Check session and auto-login if needed
        if not await self.session_manager.is_logged_in():
            logger.warning("Session expired or missing. Performing automatic login.")
            success = await self.session_manager.login_to_cvlibrary()
            if not success:
                logger.error("Failed to automatically log in. Cannot proceed with search.")
                return False
            
            # Go back to search page
            logger.info("Navigating back to candidate search...")
            await self.page.goto(self.search_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)
        else:
            logger.info("Session valid.")

        # 1. Fill Keywords (Boolean)
        keywords_selectors = [
            "textarea[name='keywords']",
            "textarea.cvsearchKeywords",
            "input#keywords",
            "input[name='keywords']"
        ]
        keywords_filled = False
        for selector in keywords_selectors:
            try:
                locator = self.page.locator(selector).first
                # Wait for element to be visible/present
                await locator.wait_for(state="attached", timeout=3000)
                if await locator.is_visible():
                    await locator.fill(boolean_keywords)
                    logger.info("Filled search keywords.")
                    keywords_filled = True
                    break
            except Exception:
                continue

        if not keywords_filled:
            page_title = await self.page.title()
            logger.error(f"Could not find keywords input field on CV-Library Search page! Current URL: {self.page.url} | Title: {page_title}")
            return False

        # 2. Submitted since: change to custom search period
        submitted_selectors = [
            "select#time",
            "select[name='time']",
            "select#templated_age",
            "select[name='templated_age']"
        ]
        submitted_selected = False
        for selector in submitted_selectors:
            try:
                locator = self.page.locator(selector).first
                await locator.wait_for(state="attached", timeout=2000)
                if await locator.is_visible():
                    try:
                        await locator.select_option(label=search_period)
                    except Exception:
                        await locator.select_option(value=search_period)
                    logger.info(f"Set 'Submitted Since' to {search_period}.")
                    submitted_selected = True
                    break
            except Exception:
                continue

        if not submitted_selected:
            logger.warning("Could not set 'Submitted Since' automatically, proceeding with page default.")

        # 3. Click More Search Options
        more_options_selectors = [
            ".toggle-quick-advanced",
            "text='MORE SEARCH OPTIONS'",
            "button:has-text('MORE SEARCH OPTIONS')"
        ]
        more_options_clicked = False
        for selector in more_options_selectors:
            try:
                locator = self.page.locator(selector).first
                await locator.wait_for(state="attached", timeout=2000)
                # Dispatch click via JS to bypass hidden/overlapping layout checks
                await locator.dispatch_event("click")
                logger.info("Clicked 'MORE SEARCH OPTIONS'.")
                more_options_clicked = True
                await asyncio.sleep(1)
                break
            except Exception:
                continue

        # 4. Hide recently viewed candidates
        try:
            input_locator = self.page.locator("input#hide_recently_viewed_candidates, input[name='hide_recently_viewed_candidates']").first
            await input_locator.wait_for(state="attached", timeout=3000)
            
            # Use direct Javascript to force the state and trigger standard event bubbling
            await input_locator.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); }")
            logger.info("Checked 'Hide recently viewed candidates' via direct DOM dispatch.")
        except Exception as e:
            logger.error(f"Failed to check 'Hide recently viewed candidates': {e}")

        # 5. Click Search CVs
        search_btn_selectors = [
            "#submit_cv_search",
            "input[name='submit_cv_search']",
            "input[value='Search CVs']",
            "button:has-text('Search CVs')"
        ]
        search_clicked = False
        for selector in search_btn_selectors:
            try:
                locator = self.page.locator(selector).first
                await locator.wait_for(state="attached", timeout=3000)
                await locator.dispatch_event("click")
                logger.info("Clicked 'Search CVs' via dispatch_event. Waiting for results...")
                search_clicked = True
                break
            except Exception:
                continue

        if not search_clicked:
            logger.error("Could not click 'Search CVs' button!")
            return False

        # Wait for search results page to load candidate results
        try:
            logger.info("Waiting for candidate search results URL...")
            # Wait for URL to contain search query parameters indicating navigation has occurred
            await self.page.wait_for_url(lambda url: "submit_cv_search" in url or "enc_keywords" in url or "posted" in url or "time=" in url, timeout=15000)
            logger.info("Search results page navigation complete.")
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"Timeout waiting for results page navigation: {e}. Proceeding anyway...")
            await asyncio.sleep(4)

        # Now start processing results
        work_done = await self.process_all_search_pages(cv_parser, ai_mgr, tracker, criteria_text, supabase_writer)
        return work_done

    async def process_all_search_pages(self, cv_parser, ai_mgr, tracker, criteria_text, supabase_writer):
        """Iterates through search result pages and processes candidate CVs."""
        page_num = 1
        work_done = False

        while True:
            logger.info(f"Processing Search Results Page {page_num}...")
            
            # Find all candidate profile elements (exact text match to avoid View CV Watchdogs etc.)
            view_cv_locators = self.page.locator("a:text-is('View CV')")
            count = await view_cv_locators.count()
            logger.info(f"Found {count} CVs on page {page_num}.")
            
            if count == 0:
                logger.info("No CVs to process on this page.")
                break

            # Collect all CV links and names from the current page
            candidates = []
            for i in range(count):
                try:
                    locator = view_cv_locators.nth(i)
                    href = await locator.get_attribute("href")
                    if href:
                        if not href.startswith("http"):
                            href = "https://www.cv-library.co.uk" + href
                        
                        if "/recruiter/cv/" not in href and "/view-cv/" not in href and "recruiter/cv" not in href:
                            continue
                            
                        ref_match = re.search(r"cv/(\d+)", href)
                        cv_id = ref_match.group(1) if ref_match else href
                        
                        # Find the parent card containing this specific locator
                        card = self.page.locator("li").filter(has=locator).first
                        if await card.count() == 0:
                            card = self.page.locator("div.search-result, div.cv-card, div.search-results__item").filter(has=locator).first
                        
                        name = "Unknown"
                        if await card.count() > 0:
                            # Find the candidate name h2 inside this specific card
                            name_el = card.locator("h2").first
                            if await name_el.count() > 0:
                                name = await name_el.inner_text()
                                name = name.strip()
                        
                        if not name or name == "Unknown":
                            # Try matching first visible heading/link inside the card
                            name_el = card.locator("h3, a.candidate-name").first
                            if await name_el.count() > 0:
                                name = await name_el.inner_text()
                                name = name.strip()

                        # Fallback filtering to remove text noise
                        if name:
                            name = name.replace("View CV", "").strip()

                        candidates.append({
                            "cv_id": cv_id,
                            "cv_link": href,
                            "name": name if name else "Unknown",
                            "location": "Unknown" # fallback to AI extraction
                        })
                except Exception as e:
                    logger.error(f"Error reading candidate card index {i}: {e}")

            # Process candidates sequentially
            for candidate in candidates:
                cv_id = candidate["cv_id"]
                cv_link = candidate["cv_link"]
                
                if tracker.is_processed(cv_id):
                    logger.info(f"Skipping already processed CV ID: {cv_id}")
                    continue

                logger.info(f"Processing candidate: {candidate['name']} (ID: {cv_id})")
                
                # Check session during processing
                if not await self.session_manager.is_logged_in():
                    logger.warning("Session expired during processing. Re-authenticating.")
                    success = await self.session_manager.login_to_cvlibrary()
                    if success:
                        logger.info("Re-authentication successful.")
                    else:
                        logger.error("Re-authentication failed. Stopping processing.")
                        break

                # Fetch Plain Text CV
                cv_text = await cv_parser.extract_cv_text(cv_link)
                if cv_text:
                    work_done = True
                    # Run AI Classifier
                    ai_result = ai_mgr.classify_candidate(cv_text, criteria_text, expected_name=candidate["name"])
                    
                    if ai_result.get("classification") == "ERROR":
                        error_msg = ai_result.get("reasoning", "").lower()
                        if "insufficient_quota" in error_msg or "balance" in error_msg or "limit" in error_msg or "429" in error_msg:
                            logger.error("AI API limit or balance reached. Stopping processing to prevent skipping CVs.")
                            return False # Stop the entire search flow

                        logger.error(f"AI error for CV {cv_id}. Skipping and NOT adding to processed tracker.")
                        continue
                        
                    full_data = {
                        "name": candidate["name"] if candidate["name"] != "Unknown" else ai_result.get("candidate_name", "Unknown"),
                        "location": candidate["location"] if candidate["location"] != "Unknown" else ai_result.get("location", "Unknown"),
                        "cv_id": cv_id,
                        "cv_link": cv_link,
                        "platform_name": "CV-Library Search"
                    }
                    full_data = {**full_data, **ai_result}
                    
                    # Save to Supabase
                    supabase_writer.append_candidate(full_data)
                    
                    # Track as processed
                    tracker.add(cv_id)
                    logger.info("Simulating human review... waiting 10 seconds before the next CV.")
                    await asyncio.sleep(10)

            # Pagination handling: look for "Next" page button
            next_btn_selectors = [
                "a:has-text('Next')",
                "a.next",
                "a[rel='next']",
                ".pagination__next",
                "a:has-text('next')"
            ]
            next_clicked = False
            for selector in next_btn_selectors:
                try:
                    locator = self.page.locator(selector).first
                    if await locator.is_visible():
                        is_disabled = await locator.get_attribute("class")
                        if is_disabled and "disabled" in is_disabled.lower():
                            continue
                        
                        await locator.click()
                        logger.info("Clicked Next Page.")
                        next_clicked = True
                        page_num += 1
                        await self.page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(3)
                        break
                except Exception:
                    continue

            if not next_clicked:
                logger.info("No more pages found or 'Next' button is disabled. Search processing complete.")
                break

        return work_done
