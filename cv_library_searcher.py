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

    async def run_search_flow(self, boolean_keywords, cv_parser, ai_mgr, tracker, supabase_writer, search_period="24 hours"):
        """Performs search on CV-Library and processes all matching CVs."""
        # Always start a fresh search
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

        # 1. Fill Keywords (Boolean) via JS to bypass custom UI widgets
        try:
            # The search builder often hides the real textarea and uses a complex tag-input widget. 
            # We inject the value directly into the real textarea that gets submitted.
            js_code = f"""
            () => {{
                let ta = document.querySelector("textarea[name='keywords']") || document.querySelector("input#keywords");
                if(ta) {{
                    ta.value = `{boolean_keywords}`;
                    ta.style.display = 'block'; // Ensure it can be seen/submitted if needed
                    ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            }}
            """
            success = await self.page.evaluate(js_code)
            if success:
                logger.info("Filled search keywords via direct DOM injection.")
                keywords_filled = True
            else:
                # Fallback to standard fill
                locator = self.page.locator("input.boolean__input, textarea[name='keywords'], input#keywords").first
                if await locator.is_visible():
                    await locator.fill(boolean_keywords)
                    keywords_filled = True
        except Exception as e:
            logger.error(f"Error filling keywords: {e}")

        if not keywords_filled:
            content = await self.page.content()
            with open("cloudflare_page.html", "w", encoding="utf-8") as f:
                f.write(content)
            
            page_title = await self.page.title()
            logger.info(f"Page title: {page_title}")
            logger.error(f"Could not find keywords input field on CV-Library Search page! Current URL: {self.page.url} | Title: {page_title}")
            return False

        # 2. Submitted since: change to custom search period via JS
        try:
            js_code = f"""
            () => {{
                let select = document.querySelector("select[name='time']") || document.querySelector("select#search-builder__time") || document.querySelector("select#time");
                if(select) {{
                    select.value = '{search_period}';
                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }}
                return false;
            }}
            """
            success = await self.page.evaluate(js_code)
            if success:
                logger.info(f"Set 'Submitted Since' to {search_period} via direct DOM injection.")
            else:
                logger.warning("Could not find 'Submitted Since' select field in DOM.")
        except Exception as e:
            logger.warning(f"Error setting 'Submitted Since': {e}")

                # [DISABLED] Click More Search Options & Hide recently viewed candidates
        # # 3. Click More Search Options
        # more_options_selectors = [
        # ".toggle-quick-advanced",
        # "text='MORE SEARCH OPTIONS'",
        # "button:has-text('MORE SEARCH OPTIONS')"
        # ]
        # more_options_clicked = False
        # for selector in more_options_selectors:
        # try:
        # locator = self.page.locator(selector).first
        # await locator.wait_for(state="attached", timeout=2000)
        # # Dispatch click via JS to bypass hidden/overlapping layout checks
        # await locator.dispatch_event("click")
        # logger.info("Clicked 'MORE SEARCH OPTIONS'.")
        # more_options_clicked = True
        # await asyncio.sleep(1)
        # break
        # except Exception:
        # continue
        # 
        # # 4. Hide recently viewed candidates
        # try:
        # input_locator = self.page.locator("input#hide_recently_viewed_candidates, input[name='hide_recently_viewed_candidates']").first
        # await input_locator.wait_for(state="attached", timeout=3000)
        # 
        # # Use direct Javascript to force the state and trigger standard event bubbling
        # await input_locator.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('change', { bubbles: true })); }")
        # logger.info("Checked 'Hide recently viewed candidates' via direct DOM dispatch.")
        # except Exception as e:
        # logger.error(f"Failed to check 'Hide recently viewed candidates': {e}")
        # 
        # 
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
        work_done = await self.process_all_search_pages(cv_parser, ai_mgr, tracker, supabase_writer)
        return work_done

    async def process_all_search_pages(self, cv_parser, ai_mgr, tracker, supabase_writer):
        """Iterates through search result pages and processes candidate CVs."""
        page_num = 1
        work_done = False

        while True:
            logger.info(f"Processing Search Results Page {page_num}...")
            # --- INFINITE LOOP PROTECTION ---
            try:
                current_ids = await self.page.evaluate('''() => {
                    return Array.from(document.querySelectorAll('.candidate-identifier-container, [data-candidate-id], .candidate-name')).map(el => el.getAttribute('data-candidate-id') || el.innerText || '').filter(Boolean);
                }''')
                current_ids_str = ",".join(sorted(current_ids))
                if hasattr(self, 'last_page_ids') and getattr(self, 'last_page_ids') == current_ids_str and current_ids_str != "":
                    logger.warning("Infinite loop detected: Candidate IDs exactly identical to previous page. Breaking pagination.")
                    break
                self.last_page_ids = current_ids_str
            except Exception as e:
                logger.debug(f"Loop protection check failed: {e}")
            # --------------------------------

            
            # Find all candidate profile elements (exact text match to avoid View CV Watchdogs etc.)
            view_cv_locators = self.page.locator("a:text-is('View CV')")
            count = await view_cv_locators.count()
            logger.info(f"Found {count} CVs on page {page_num}.")
            
            if count == 0:
                logger.info("No CVs to process on this page. Dumping HTML for debugging.")
                content = await self.page.content()
                with open("empty_results.html", "w", encoding="utf-8") as f:
                    f.write(content)
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

                        # --- FAST SKIP OPTIMIZATION ---
                        # Check the database BEFORE we waste time extracting Name, Job Title, etc. from HTML
                        if tracker.is_processed(cv_id, "Legacy"):
                            logger.info(f"Skipping already processed CV ID: {cv_id} (bypassed HTML extraction)")
                            continue
                        # ------------------------------
                        
                        card = self.page.locator("li").filter(has=locator).first
                        if await card.count() == 0:
                            card = self.page.locator("div.search-result, div.cv-card, div.search-results__item, article, .search-card, .search-card__candidate").filter(has=locator).first
                            if await card.count() == 0:
                                # Final fallback: Find the closest li, article, or exact search-result div
                                card = locator.locator("xpath=ancestor::li[1] | ancestor::article[1] | ancestor::div[@class='search-result' or contains(@class, 'search-result-item')][1]").first
                                
                        name = "Unknown"
                        location = "Unknown"
                        job_title = "Unknown"
                        desired_role = "Unknown"
                        update_str = "Legacy"
                        card_text = ""
                        
                        if await card.count() > 0:
                            card_text = await card.inner_text()
                            card_html = await card.inner_html()
                            
                            with open("/root/cvl_debug.txt", "a") as f:
                                f.write(f"\n--- NEW CARD ---\nTEXT:\n{card_text}\n\nHTML:\n{card_html}\n-----------------\n")

                            # Fallback Regex Extractions
                            m_jt = re.search(r'Job Title\s*[:\n]\s*([^\n]+)', card_text, re.IGNORECASE)
                            if m_jt: job_title = m_jt.group(1).strip()
                                
                            m_dr = re.search(r'Desired Role\s*[:\n]\s*([^\n]+)', card_text, re.IGNORECASE)
                            if m_dr: desired_role = m_dr.group(1).strip()
                                
                            m_loc = re.search(r'Location\s*[:\n]\s*([^\n]+)', card_text, re.IGNORECASE)
                            if m_loc: location = m_loc.group(1).strip()
                            
                            # DOM-based Job Title Extraction (CV-Library often places it in h3, or a class)
                            if job_title == "Unknown":
                                jt_el = card.locator(".job-title, [class*='job-title'], .candidate-job-title").first
                                if await jt_el.count() > 0:
                                    jt_text = await jt_el.inner_text()
                                    if jt_text: job_title = jt_text.split('\n')[0].strip()

                            # DOM-based Location Extraction
                            if location == "Unknown":
                                loc_el = card.locator(".location, [class*='location'], dd.location, dd[title='Location']").first
                                if await loc_el.count() > 0:
                                    loc_text = await loc_el.inner_text()
                                    if loc_text: location = loc_text.split('\n')[0].strip()

                            # DOM-based Name Extraction
                            # If name is hidden, it will fall back to "Unknown"
                            name_el = card.locator("h2.candidate-name, h2, h3").first
                            if await name_el.count() > 0:
                                n = await name_el.inner_text()
                                n = n.split('\n')[0].strip()
                                if "View CV" not in n and "Match" not in n and n:
                                    name = n
                                    
                            # Sometimes the Name is in h2, and Job Title is in the very next h3
                            if job_title == "Unknown":
                                next_h3 = card.locator("h3").first
                                if await next_h3.count() > 0:
                                    h3_text = await next_h3.inner_text()
                                    h3_text = h3_text.split('\n')[0].strip()
                                    if h3_text and h3_text != name and "View CV" not in h3_text:
                                        job_title = h3_text

                        candidates.append({
                            "cv_id": cv_id,
                            "cv_link": href,
                            "name": name if name else "Unknown",
                            "location": location,
                            "update_str": update_str,
                            "job_title": job_title,
                            "desired_role": desired_role
                        })
                except Exception as e:
                    logger.error(f"Error reading candidate card index {i}: {e}")

            # Process candidates sequentially
            for candidate in candidates:
                cv_id = candidate["cv_id"]
                cv_link = candidate["cv_link"]
                update_str = candidate.get("update_str", "Legacy")
                
                if tracker.is_processed(cv_id, update_str):
                    logger.info(f"Skipping already processed and viewed recently CV ID: {cv_id}")
                    continue

                logger.info(f"Processing candidate: {candidate['name']} (ID: {cv_id})")

                # --- FAST PRE-SCREENING ON TITLE & DESIRED ROLE ---
                job_title = candidate.get("job_title", "Unknown")
                desired_role = candidate.get("desired_role", "Unknown")
                
                job_title_lower = job_title.lower()
                desired_role_lower = desired_role.lower()
                # Null/blank job title values from CV-Library profile - skip pre-screen and read full CV
                NULL_TITLE_VALUES = {"n/a", "na", "none", "null", "", "unknown", "-", "not specified", "not available"}
                title_is_blank = job_title_lower.strip() in NULL_TITLE_VALUES
                desired_is_blank = desired_role_lower.strip() in NULL_TITLE_VALUES

                bypass_keywords = ["unemploy", "freelance"]
                
                if title_is_blank and desired_is_blank:
                    # Both title and desired role are blank/n/a - cannot pre-screen, must read full CV
                    logger.info(f"Candidate {candidate['name']} has no job title or desired role (n/a/blank). Bypassing pre-screen to read full CV.")
                    pre_decision = {"classification": "FIT", "reasoning": "Bypassed pre-screen: no title data available, will read full CV."}
                elif any(kw in job_title_lower or kw in desired_role_lower for kw in bypass_keywords):
                    logger.info(f"Candidate {candidate['name']} has 'unemployed/freelance' in title. Bypassing fast pre-screen to read full CV.")
                    pre_decision = {"classification": "FIT", "reasoning": "Bypassed pre-screen due to unemployed/freelance title."}
                else:
                    logger.info(f"Running LLM Pre-Screen on Candidate: {candidate['name']}")
                    pre_decision = ai_mgr.fast_title_prescreen(job_title, desired_role)
                if pre_decision.get("classification") == "UNFIT":
                    reason = pre_decision.get("reasoning", "Pre-screen Unfit")
                    logger.info(f"Candidate {candidate['name']} PRE-CLASSIFIED AS UNFIT. Reason: {reason}")
                    full_data = {
                        "cv_id": cv_id,
                        "name": candidate['name'],
                        "location": candidate.get('location', 'Unknown'),
                        "current_company": "Unknown",
                        "current_position": job_title,
                        "job_title": job_title,
                        "desired_role": desired_role,
                        "classification": "UNFIT",
                        "reasoning": f"Pre Screening: {reason}",
                        "t1_tenure": None,
                        "t2_tenure": None,
                        "business_specialization": "Unknown",
                        "linkedin_url": None,
                        "salary_range": None,
                        "email": None,
                        "phone_number": None,
                        "cv_link": candidate['cv_link'],
                        "platform_name": "CV-Library",
                        "dcm_type": os.getenv("DCM_TYPE", "Unknown")
                    }
                    if supabase_writer:
                        supabase_writer.append_candidate(full_data)
                    tracker.add(cv_id, update_str)
                    continue
                # --------------------------------------------------

                
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
                    ai_result = ai_mgr.classify_candidate(cv_text, expected_name=candidate["name"])
                    
                    if ai_result.get("classification") in ["ERROR", "TOKEN_ERROR"]:
                        error_msg = ai_result.get("reasoning", "").lower()
                        if "insufficient_quota" in error_msg or "balance" in error_msg or "limit" in error_msg or "429" in error_msg:
                            logger.error("AI API limit or balance reached. Stopping processing to prevent skipping CVs.")
                            import discord_alert; discord_alert.pause_and_alert() # Auto-Resume added

                        logger.error(f"AI error for CV {cv_id}. Skipping and NOT adding to processed tracker.")
                        continue
                        
                    if ai_result.get("classification") == "FIT":
                        revealed = await cv_parser.reveal_contact_details()
                        if revealed:
                            contact_info = await cv_parser.get_contact_details_from_page()
                            if contact_info.get("email"):
                                ai_result["email"] = contact_info["email"]
                            if contact_info.get("phone"):
                                ai_result["phone_number"] = contact_info["phone"]
                            if contact_info.get("linkedin"):
                                ai_result["linkedin_url"] = contact_info["linkedin"]
                        
                    full_data = {
                        "name": candidate["name"] if candidate["name"] != "Unknown" else ai_result.get("candidate_name", "Unknown"),
                        "location": candidate["location"] if candidate["location"] != "Unknown" else ai_result.get("location", "Unknown"),
                        "cv_id": cv_id,
                        "cv_link": cv_link,
                        "platform_name": "CV-Library",
                        "dcm_type": os.getenv("DCM_TYPE", "Unknown"),
                        "job_title": candidate.get("job_title", "Unknown") if candidate.get("job_title", "Unknown") != "Unknown" else ai_result.get("current_position", "Unknown"),
                        "desired_role": candidate.get("desired_role", "Unknown") if candidate.get("desired_role", "Unknown") != "Unknown" else ai_result.get("desired_role", "Unknown")
                    }
                    full_data = {**full_data, **ai_result}
                    
                    # Save to Supabase
                    supabase_writer.append_candidate(full_data)
                    
                    # Track as processed
                    tracker.add(cv_id, update_str)
                    logger.info("Simulating human review... waiting 5 seconds before the next CV.")
                    await asyncio.sleep(5)


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
