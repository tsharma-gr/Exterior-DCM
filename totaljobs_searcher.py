import asyncio
import re
import json
import os
from logger_config import logger
from playwright.async_api import Page
from session_manager import SessionManager

class TotalJobsSearcher:
    def __init__(self, page: Page, context):
        self.page = page
        self.context = context
        self.search_url = "https://recruiter.totaljobs.com/CandidateSearchWebMVC/CandidateSearch"
        self.session_manager = SessionManager(page, context)

    async def robust_fill(self, selectors, text):
        """Finds a visible text input/textarea and fills it with robust fallback evaluation."""
        for selector in selectors:
            try:
                locator = self.page.locator(selector)
                count = await locator.count()
                for idx in range(count):
                    el = locator.nth(idx)
                    if await el.is_visible():
                        await el.scroll_into_view_if_needed()
                        await el.click(force=True)
                        try:
                            await el.fill("")
                            await el.fill(text)
                        except Exception:
                            pass
                        escaped_text = json.dumps(text)
                        await el.evaluate(f"el => {{ el.value = {escaped_text}; el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }})); }}")
                        logger.info(f"Filled visible field using selector: {selector} (index {idx})")
                        return True
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
        return False

    async def navigate_to_search(self, use_boolean_tab=False):
        """Navigates to TotalJobs Candidate Search and ensures correct Search/Targeted tab is selected."""
        logger.info(f"Navigating to TotalJobs Candidate Search: {self.search_url}")
        await self.page.goto(self.search_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)

        # Handle cookie consent or similar banners if they pop up
        cookie_selectors = [
            "#ccm-accept-all-btn",
            "#onetrust-accept-btn-handler",
            "button:has-text('Accept All')",
            "button:has-text('Accept cookies')"
        ]
        for sel in cookie_selectors:
            try:
                btn = self.page.locator(sel).first
                if await btn.is_visible():
                    await btn.click()
                    logger.info("Dismissed cookie consent banner on TotalJobs.")
                    await asyncio.sleep(1)
                    break
            except Exception:
                pass

        # Check if redirected to login page
        import os
        current_url = self.page.url
        is_login_page = ("login" in current_url.lower() or 
                         "signin" in current_url.lower() or 
                         "returnurl" in current_url.lower() or
                         await self.page.locator("input[type='email']").count() > 0 or 
                         await self.page.locator("input[type='password']").count() > 0)
        
        if is_login_page:
            logger.warning("TotalJobs Session missing or expired. Attempting automatic login...")
            success = await self.session_manager.login_to_totaljobs()
            if not success:
                logger.error("Automatic login failed. Cannot proceed with TotalJobs search.")
                return False
            
            # Go back to search page
            logger.info("Navigating back to candidate search...")
            await self.page.goto(self.search_url, wait_until="domcontentloaded")
            await asyncio.sleep(3)

        # Ensure correct search tab is selected
        tab_name = "Search" if use_boolean_tab else "Targeted"
        logger.info(f"Checking for '{tab_name}' tab...")
        try:
            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3) # Wait for page elements to settle/render
            search_tab = self.page.locator(f"a:text-is('{tab_name}'), [role='tab']:text-is('{tab_name}'), li:not(.active):has-text('{tab_name}')").first
            if await search_tab.count() > 0:
                await search_tab.click(force=True)
                logger.info(f"Successfully clicked '{tab_name}' tab.")
                await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Error while switching to {tab_name} tab: {e}")

    async def run_search_flow(self, boolean_keywords, cv_parser, ai_mgr, tracker, output_mgr, search_period="24 hours"):
        # Check if running in Cron Mode (nightly automated run)
        import os
        if os.getenv("CRON_MODE", "false").lower() == "true" and os.getenv("RUN_TOTALJOBS", "false").lower() != "true":
            logger.info("TotalJobs search is disabled in nightly automated runs. Skipping...")
            return False

        """Fills the TotalJobs Search form and submits the search."""
        use_boolean_tab = "and" in boolean_keywords.lower() or "comcat" in boolean_keywords.lower()
        has_results = False
        if "candidatesearch" in self.page.url.lower():
            indicators = self.page.locator("div.candidate-identifier-container, div.candidate-card, div.card-row-container")
            if await indicators.count() > 0:
                logger.info("Already on search results page. BUT forcing new search for boolean.")
                has_results = False # Force to false to always search
                
        if not has_results:
            await self.navigate_to_search(use_boolean_tab=use_boolean_tab)
    
            logger.info("Parsing boolean keywords...")
            
            if use_boolean_tab:
                logger.info("Using 'Search' tab. Filling entire boolean query into main keywords field...")
                cv_kw_selectors = [
                    "#txtBooleanMvc",
                    "[name='FreeText']",
                    "input[placeholder*='keywords' i]",
                    "textarea[placeholder*='keywords' i]",
                    "input[placeholder*='Boolean' i]",
                    "textarea[placeholder*='Boolean' i]"
                ]
                cv_filled = await self.robust_fill(cv_kw_selectors, boolean_keywords)
                if not cv_filled:
                    logger.warning("Could not fill keywords using standard selectors, trying broad textarea/input fallback...")
                    await self.robust_fill(["textarea", "input"], boolean_keywords)
            else:
                logger.info("Using 'Targeted' tab. Splitting keywords and filling standard fields...")
                # Smart split: find the first instance of ") AND (" to avoid splitting inside brackets
                if ") AND (" in boolean_keywords:
                    parts = boolean_keywords.split(") AND (", 1)
                    cv_keywords = parts[0].strip() + ")" # Put back the closing bracket
                    job_title_keywords = "(" + parts[1].strip() # Put back the opening bracket
                else:
                    # Fallback to normal split if no explicit boundary
                    import re
                    parts = re.split(r'\s+AND\s+', boolean_keywords, maxsplit=1, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        cv_keywords = parts[0].strip()
                        job_title_keywords = parts[1].strip()
                    else:
                        # If there's no AND at all, the entire string should go to Job Titles
                        cv_keywords = ""
                        job_title_keywords = boolean_keywords

                # 1. Fill "Search anything in CV or Profile"
                logger.info("Filling 'Search anything in CV or Profile'...")
                cv_kw_selectors = [
                    "#txtBooleanMvc",
                    "[name='FreeText']",
                    "input[placeholder*='keywords' i]",
                    "textarea[placeholder*='keywords' i]",
                    "input[placeholder*='Boolean' i]",
                    "textarea[placeholder*='Boolean' i]"
                ]
                cv_filled = await self.robust_fill(cv_kw_selectors, cv_keywords)
                if not cv_filled:
                    logger.warning("Could not fill CV keywords using standard selectors, trying broad textarea/input fallback...")
                    await self.robust_fill(["textarea", "input"], cv_keywords)

                # 2. Select CV in CV/Profile dropdown
                logger.info("Selecting 'CV' in CV/Profile dropdown...")
                try:
                    cv_select = self.page.locator("select[name*='CV' i], select[id*='CV' i], select:has(option:text-is('CV')), select:has(option:text-is('CV only')), select:has(option:text-is('CV Only'))").first
                    if await cv_select.count() > 0:
                        await cv_select.evaluate("el => { el.removeAttribute('disabled'); el.classList.remove('targeted-search-disable'); }")
                        options = await cv_select.locator("option").all_inner_texts()
                        for opt in options:
                            if opt.strip().lower() in ["cv", "cv only", "cvonly"]:
                                await cv_select.select_option(label=opt)
                                logger.info(f"Selected option '{opt}' in CV/Profile dropdown.")
                                break
                    else:
                        first_select = self.page.locator("select").first
                        if await first_select.is_visible():
                            await first_select.evaluate("el => el.removeAttribute('disabled')")
                            await first_select.select_option(index=1)
                            logger.info("Selected index 1 of first select dropdown.")
                except Exception as e:
                    logger.error(f"Failed to select CV option: {e}")

                # 3. Fill "Search in Job Titles"
                if job_title_keywords:
                    logger.info("Filling 'Search in Job Titles'...")
                    title_kw_selectors = [
                        "#jobTitlesMvc",
                        "[name='FreeTextJobTitles']",
                        "input[placeholder*='Marketing' i]",
                        "textarea[placeholder*='Marketing' i]",
                        "input[placeholder*='Job Title' i]",
                        "textarea[placeholder*='Job Title' i]"
                    ]
                    await self.robust_fill(title_kw_selectors, job_title_keywords)

                # 4. Select Current in Current/Desired dropdown
                logger.info("Selecting 'Current' in Current/Desired dropdown...")
                try:
                    current_select = self.page.locator("select[name*='Current' i], select[id*='Current' i], select:has(option:text-is('Current')), select:has(option:text-is('Current only')), select:has(option:text-is('Current Position'))").first
                    if await current_select.count() > 0:
                        await current_select.evaluate("el => { el.removeAttribute('disabled'); el.classList.remove('targeted-search-disable'); }")
                        options = await current_select.locator("option").all_inner_texts()
                        for opt in options:
                            if opt.strip().lower() in ["current", "current only", "current position"]:
                                await current_select.select_option(label=opt)
                                logger.info(f"Selected option '{opt}' in Current/Desired dropdown.")
                                break
                    else:
                        selects = self.page.locator("select")
                        if await selects.count() > 1:
                            sel = selects.nth(1)
                            await sel.evaluate("el => el.removeAttribute('disabled')")
                            await sel.select_option(index=1)
                            logger.info("Selected index 1 of second select dropdown.")
                except Exception as e:
                    logger.error(f"Failed to select Current option: {e}")

            logger.info("Filling Location 'UK'...")
            try:
                loc_selectors = [
                    "input[placeholder*='Location or postcode']",
                    "input[name*='Location' i]",
                    "input#Location",
                    "input[placeholder*='town, city or postcode']"
                ]
                for sel in loc_selectors:
                    loc_input = self.page.locator(sel).first
                    if await loc_input.is_visible():
                        await loc_input.fill("UK")
                        await asyncio.sleep(1.5)
                        await loc_input.press("ArrowDown")
                        await asyncio.sleep(0.5)
                        await loc_input.press("Enter")
                        logger.info("Filled location 'UK'.")
                        break
            except Exception as e:
                logger.error(f"Failed to fill location: {e}")

            # Advanced search & Country of residence disabled to prevent ASP.NET AJAX form reset

            logger.info("Selecting '1 day' in Search Time/Updated dropdown...")
            try:
                search_period = "1 day"
                
                # To avoid Playwright selector parsing errors, we will find the select programmatically or use safe selectors
                active_select = None
                selectors_to_try = [
                    "select:has(option:text-is('1 day'))",
                    "select:has(option:text-is('24 hours'))",
                    "select:has(option:text-is('Today'))",
                    "select[name*='LastActivity' i]",
                    "select[name*='Activity' i]"
                ]
                for sel in selectors_to_try:
                    loc = self.page.locator(sel).first
                    if await loc.count() > 0:
                        active_select = loc
                        break
                        
                if not active_select:
                    # Try finding by label texts
                    for label_text in ["Active within", "Updated", "Hide Profiles viewed since"]:
                        loc = self.page.locator(f"text='{label_text}'").locator("xpath=following::select[1]").first
                        if await loc.count() > 0:
                            active_select = loc
                            break
                
                if active_select and await active_select.count() > 0:
                    await active_select.evaluate("el => { el.removeAttribute('disabled'); el.style.display = 'block'; }")
                    js_select_script = f"""
                        el => {{
                            const target = "{search_period}".toLowerCase().trim();
                            for (let i = 0; i < el.options.length; i++) {{
                                const optText = el.options[i].text.toLowerCase().trim();
                                if (optText === target || 
                                    (target === "1 day" && optText.includes("24 hours")) || 
                                    (target === "1 day" && optText.includes("1 day")) ||
                                    optText.includes(target)) {{
                                    el.selectedIndex = i;
                                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return el.options[i].text;
                                }}
                            }}
                            return null;
                        }}
                    """
                    selected_text = await active_select.evaluate(js_select_script)
                    # Extra robust 1-day selection using DOM clicks in case React ignores selectedIndex
                    try:
                        await self.page.evaluate('''() => {
                            const opts = document.querySelectorAll('option');
                            for (let o of opts) {
                                if (o.text.toLowerCase().includes('1 day') || o.text.toLowerCase().includes('24 hours')) {
                                    o.selected = true;
                                    o.parentElement.value = o.value;
                                    o.parentElement.dispatchEvent(new Event('change', {bubbles: true}));
                                    break;
                                }
                            }
                        }''')
                    except Exception as fallback_e:
                        pass
                    if selected_text:
                        logger.info(f"Selected option '{selected_text}' in Search Time dropdown.")
                    else:
                        logger.warning(f"Could not find '{search_period}' in options for this dropdown.")
                else:
                    logger.warning("Could not find any dropdown for time/activity (1 day). It might not exist on this page.")
            except Exception as e:
                logger.error(f"Failed to select active within option '1 day': {e}")

            logger.info("Double-checking if keyword field was cleared by UI refresh...")
            try:
                cv_kw_val = ""
                cv_kw_selectors = [
                    "#txtBooleanMvc",
                    "[name='FreeText']",
                    "input[placeholder*='keywords' i]"
                ]
                for sel in cv_kw_selectors:
                    el = self.page.locator(sel).first
                    if await el.count() > 0 and await el.is_visible():
                        cv_kw_val = await el.input_value()
                        if not cv_kw_val.strip():
                            logger.warning(f"Keyword field {sel} is empty! Refilling...")
                            if use_boolean_tab:
                                await self.robust_fill([sel], boolean_keywords)
                            else:
                                await self.robust_fill([sel], cv_keywords)
                        break
            except Exception as e:
                logger.error(f"Failed to double-check keyword field: {e}")

            logger.info("Submitting search...")
            try:
                search_buttons = [
                    "button.btn-search",
                    "button#btnSearch",
                    "button[type='submit']:has-text('Search')",
                    "button:has-text('Search')",
                    "input[value='Search']",
                    "a:has-text('Search')",
                    "span:has-text('Search')"
                ]
                search_clicked = False
                for btn_sel in search_buttons:
                    btn = self.page.locator(btn_sel).filter(visible=True).last
                    if await btn.count() > 0:
                        await btn.evaluate("el => el.click()")
                        logger.info(f"Clicked Search button using selector: {btn_sel}")
                        search_clicked = True
                        break
                if not search_clicked:
                    logger.warning("Could not click Search button automatically.")
            except Exception as e:
                logger.error(f"Failed to click Search button: {e}")
            await asyncio.sleep(5)
        logger.info("Search results loaded. Processing candidates across all pages...")
        
        work_done = False
        page_num = 1
        
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

            page_work = await self.process_candidates(boolean_keywords, cv_parser, ai_mgr, tracker, output_mgr)
            if page_work:
                work_done = True
            
            # Find the "Next Page" button
            next_btn = None
            next_selectors = [
                "a:text-is('>')",
                "a:has-text('>')",
                "a.next",
                "a[class*='next' i]",
                "a[aria-label*='Next' i]",
                "li.next a",
                "button.next",
                "button:has-text('>')",
                ".pagination .next a"
            ]
            
            for selector in next_selectors:
                loc = self.page.locator(selector).filter(visible=True).first
                if await loc.count() > 0:
                    next_btn = loc
                    break
            
            if next_btn and await next_btn.is_visible() and await next_btn.is_enabled():
                class_attr = await next_btn.get_attribute("class") or ""
                if "disabled" in class_attr.lower() or "inactive" in class_attr.lower():
                    logger.info("Next page button exists but is disabled. Reached the last page.")
                    break
                    
                logger.info(f"Navigating to Page {page_num + 1}...")
                await next_btn.click(force=True)
                page_num += 1
                await asyncio.sleep(5) # Wait for next page to load
            else:
                logger.info("No active 'Next Page' button found. Reached the last page.")
                break
                
        return work_done

    async def process_candidates(self, boolean_keywords, cv_parser, ai_mgr, tracker, output_mgr):
        import hashlib

        async def extract_tj_roles(target):
            j_title = "Unknown"
            d_role = "Unknown"
            try:
                curr_hdr = target.locator("text='Current status'").first
                if await curr_hdr.count() > 0:
                    parent = curr_hdr.locator("xpath=..")
                    lines = (await parent.inner_text()).split('\n')
                    lines = [l.strip() for l in lines if l.strip() and l.strip().lower() != 'current status']
                    if len(lines) >= 2:
                        j_title = lines[1]
                    elif len(lines) == 1:
                        j_title = lines[0]
            except Exception as e:
                logger.debug(f"Failed to extract current status: {e}")
                
            try:
                des_hdr = target.locator("text='Desired role'").first
                if await des_hdr.count() > 0:
                    parent = des_hdr.locator("xpath=..")
                    lines = (await parent.inner_text()).split('\n')
                    lines = [l.strip() for l in lines if l.strip() and l.strip().lower() != 'desired role']
                    if len(lines) >= 2:
                        d_role = lines[1]
                    elif len(lines) == 1:
                        d_role = lines[0]
            except Exception as e:
                logger.debug(f"Failed to extract desired role: {e}")
                
            return j_title, d_role

        # Locate candidate cards. We target divs/containers that look like card rows containing candidate info.
        card_selectors = [
            "div:has(> div.candidate-identifier-container)", # The direct parent of the identifier
            "div:has(> div > div.candidate-identifier-container)", # Grandparent
            "div.candidate-card",
            "div.card-row-container",
            "div.card",
            "div[data-testid='candidate-card']",
            "li.candidate-card",
            "li.card",
            "div.candidate-row",
            "div.search-result",
            "article",
            "div[role='listitem']",
            "li[role='listitem']",
            ".candidate-profile-card"
        ]
        
        cards = None
        for selector in card_selectors:
            loc = self.page.locator(selector)
            c = await loc.count()
            if c > 0:
                # Avoid page-level wrappers like card-row-container that group all cards
                if selector in ["div.card-row-container", "div.search-result"] and c == 1:
                    logger.debug(f"Selector '{selector}' matched only 1 element. Likely a list wrapper. Skipping to fallback.")
                    continue
                cards = loc
                logger.info(f"Found {c} candidate cards using selector '{selector}'.")
                break
                
        if not cards:
            logger.warning("Could not locate candidate cards on the page using any known selectors.")
            try:
                os.makedirs("logs", exist_ok=True)
                await self.page.screenshot(path="logs/totaljobs_no_cards.png")
                logger.info("Saved debug screenshot to logs/totaljobs_no_cards.png")
                content = await self.page.content()
                with open("logs/totaljobs_no_cards.html", "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                logger.error(f"Failed to save debug screenshot: {e}")
            return False
            
        count = await cards.count()
        logger.info(f"Total candidate cards found on current view: {count}")
        
        work_done = False
        
        for i in range(count):
            try:
                card = cards.nth(i)
                if not await card.is_visible():
                    continue
                
                # Dynamically expand card to the full card container containing the experience tabs
                try:
                    for _ in range(4):
                        recent_tab = card.locator("text=Recent experience").first
                        if await recent_tab.count() > 0:
                            break
                        card = card.locator("xpath=..")
                except Exception as expand_err:
                    logger.warning(f"Failed to dynamically expand card: {expand_err}")
                
                import time
                skip_check_start = time.time()
                
                # 1. Extract Candidate Name (supports both locked text elements and unlocked anchor links)
                name_el = card.locator("div.candidate-identifier-container .identifier, div.candidate-identifier-container a, h2, h3, a[class*='name']").first
                name_text = "Unknown"
                if await name_el.count() > 0:
                    name_text = await name_el.inner_text()
                    name_text = name_text.strip()
                    name_text = re.sub(r'^\d+\.\s*', '', name_text)
                    name_text = re.sub(r'\s*\(view profile\)$', '', name_text, flags=re.I)
                    name_text = name_text.strip()
                
                if name_text == "Unknown" or not name_text:
                    # Fallback: check first heading/anchor that has class title/name, or first anchor containing text
                    for name_sel in ["h1", "h2", "h3", "h4", "a.candidate-name", "a[class*='name' i]", "div.candidate-identifier-container a", "a"]:
                        el = card.locator(name_sel).first
                        if await el.count() > 0:
                            text = await el.inner_text()
                            text = text.strip()
                            text = re.sub(r'^\d+\.\s*', '', text)
                            text = re.sub(r'\s*\(view profile\)$', '', text, flags=re.I)
                            if text and len(text) < 60 and not any(k in text.lower() for k in ["view", "invite", "unlock", "download", "share", "email", "phone"]):
                                name_text = text
                                break
                                
                if not name_text:
                    name_text = "Unknown"
                
                # 2. Extract Location (supports header subtitle with/without pipe, and fallback)
                location_text = "Unknown"
                try:
                    container_el = card.locator("div.candidate-identifier-container").first
                    if await container_el.count() > 0:
                        container_text = await container_el.inner_text() or ""
                        lines = [l.strip() for l in container_text.split("\n") if l.strip()]
                        if len(lines) >= 2:
                            # If first line is just the card number (e.g., "27."), subtitle is index 2, else index 1
                            is_number = re.match(r'^\d+\.?$', lines[0])
                            subtitle_idx = 2 if (is_number and len(lines) >= 3) else 1
                            sub_line = lines[subtitle_idx]
                            
                            if "|" in sub_line:
                                location_text = sub_line.split("|")[-1].strip()
                            else:
                                location_text = sub_line
                except Exception as e:
                    logger.debug(f"Failed to parse location from header container: {e}")

                if location_text == "Unknown" or not location_text:
                    loc_el = card.locator("div[class*='location'], span[class*='location'], div:has-text('miles')").first
                    if await loc_el.count() > 0:
                        location_text = await loc_el.inner_text()
                        location_text = location_text.replace("\n", " ").strip()
                        parts = location_text.split('|')
                        if len(parts) > 1:
                            location_text = parts[-1].strip()
                
                # 3. Create Unique Reference ID
                profile_link_el = card.locator("a[href*='profile'], a[href*='candidate']").first
                profile_url = ""
                if await profile_link_el.count() > 0:
                    profile_url = await profile_link_el.get_attribute("href") or ""
                
                if profile_url:
                    import urllib.parse
                    # Parse out candidateId query parameter if present
                    id_match = re.search(r'[?&]candidateId=([^&]+)', profile_url, re.I)
                    if id_match:
                        cv_id = urllib.parse.unquote(id_match.group(1)).strip()
                    else:
                        # Fallback to standard path regex
                        path_match = re.search(r'(?:candidate|profile|cv)/([a-zA-Z0-9_-]+)', profile_url, re.I)
                        cv_id = path_match.group(1) if path_match else None
                else:
                    cv_id = None
                    
                fallback_id = "tj_" + hashlib.md5(f"{name_text}_{location_text}".encode()).hexdigest()[:12]
                if not cv_id:
                    cv_id = fallback_id
                
                # Reconstruct a clean direct profile link prefixed with the domain
                if cv_id and not cv_id.startswith("tj_"):
                    profile_url = f"https://recruiter.totaljobs.com/CandidateSearch/CandidateDetails.aspx?candidateId={urllib.parse.quote(cv_id)}"
                elif profile_url and profile_url.startswith("/"):
                    profile_url = "https://recruiter.totaljobs.com" + profile_url
                
                # Check if processed previously in database tracker (30-day cooldown)
                force_reprocess = False
                matched_id = fallback_id if fallback_id in tracker.processed_data else cv_id
                if matched_id in tracker.processed_data:
                    last_processed_str = tracker.processed_data[matched_id].get("processed_date", "")
                    try:
                        from datetime import datetime, timedelta
                        last_processed = datetime.fromisoformat(last_processed_str)
                        days_since = (datetime.now() - last_processed).days
                        if days_since < 30:
                            check_time = round(time.time() - skip_check_start, 3)
                            logger.info(f"Candidate {name_text} (ID: {cv_id}) already processed {days_since} day(s) ago. Skipping (30-day cooldown). (Check took {check_time}s)")
                            continue
                        else:
                            logger.info(f"Candidate {name_text} (ID: {cv_id}) last processed {days_since} day(s) ago (>30 days). Re-processing!")
                            force_reprocess = True
                    except Exception:
                        logger.info(f"Candidate {name_text} (ID: {cv_id}) already processed. Skipping.")
                        continue

                # Expand card details if collapsed (clicks 'View more' link) now that we know we aren't skipping them
                try:
                    view_more = card.locator(".candidate-experience-view-more, text='View more'").first
                    if await view_more.count() > 0 and await view_more.is_visible():
                        await view_more.click(force=True)
                        logger.info("Clicked 'View more' to expand candidate card details.")
                        await asyncio.sleep(1.5)
                except Exception as view_err:
                    logger.debug(f"Could not click 'View more' expander: {view_err}")

                # Locate action buttons (Unlock/Invite) first to support locked checks
                # 4. Handle Unlock Candidate / Invite to apply
                unlock_btn = card.locator("button:has-text('Unlock candidate'), a:has-text('Unlock candidate'), [class*='unlock-candidate' i]").first
                invite_btn = card.locator("button:has-text('Invite to apply'), a:has-text('Invite to apply'), [class*='invite' i]").first
                
                # If buttons not found, check parent and grandparent containers in case the card selector was too narrow
                if not await unlock_btn.is_visible() and not await invite_btn.is_visible():
                    for level in ["..", "../..", "../../.."]:
                        parent_card = card.locator(f"xpath={level}")
                        unlock_btn = parent_card.locator("button:has-text('Unlock candidate'), a:has-text('Unlock candidate')").first
                        invite_btn = parent_card.locator("button:has-text('Invite to apply'), a:has-text('Invite to apply')").first
                        if await unlock_btn.is_visible() or await invite_btn.is_visible():
                            card = parent_card # Upgrade the card reference to the wider container
                            logger.info(f"Expanded card container to {level} to find action buttons.")
                            break

                # Sibling loop fallback to find unlock button
                if not await unlock_btn.is_visible():
                    buttons = card.locator("button, a")
                    count_btns = await buttons.count()
                    for idx in range(count_btns):
                        btn = buttons.nth(idx)
                        text = await btn.inner_text() or ""
                        title = await btn.get_attribute("title") or ""
                        class_name = await btn.get_attribute("class") or ""
                        combined_lower = (text + title + class_name).lower()
                        if "unlock candidate" in combined_lower or ("unlock" in combined_lower and "unlocked" not in combined_lower):
                            unlock_btn = btn
                            break
                            
                # Sibling loop fallback to find invite button
                if not await invite_btn.is_visible():
                    buttons = card.locator("button, a")
                    count_btns = await buttons.count()
                    for idx in range(count_btns):
                        btn = buttons.nth(idx)
                        text = await btn.inner_text() or ""
                        title = await btn.get_attribute("title") or ""
                        class_name = await btn.get_attribute("class") or ""
                        if any(x in (text + title + class_name).lower() for x in ["invite", "been-unlocked"]):
                            invite_btn = btn
                            break
                
                # Locate candidate name link
                name_link = None
                for sel in ["div.candidate-identifier-container a", "a.candidate-name", "h2 a", "h3 a", "a[class*='name' i]", "h2", "h3"]:
                    loc = card.locator(sel).first
                    if await loc.count() > 0:
                        name_link = loc
                        break
                if not name_link:
                    name_link = card.locator("a").first
                
                logger.info(f"Processing candidate card {i+1}/{count}: {name_text} (ID: {cv_id})")
                
                # Extract Metadata directly from the card preview
                extracted_job_title = "Unknown"
                extracted_desired_role = "Unknown"
                
                # 1. Extract Job Title from Recent Experience with multi-line backtracking
                try:
                    card_lines = [l.strip() for l in (await card.inner_text() or "").split("\n") if l.strip()]
                    for idx, line in enumerate(card_lines):
                        match = re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\b', line, re.I)
                        if match:
                            candidate_title = "Unknown"
                            # If date starts later on the line, grab the prefix
                            if match.start() > 2:
                                candidate_title = line[:match.start()].strip()
                            else:
                                # Look at preceding lines (usually title is idx-2 if company is idx-1, or idx-1)
                                if idx >= 2:
                                    potential_title = card_lines[idx - 2]
                                    if not any(x in potential_title.lower() for x in ["recent experience", "other cv snippets", "applications", "never unlocked"]):
                                        candidate_title = potential_title
                                if candidate_title == "Unknown" and idx >= 1:
                                    potential_title = card_lines[idx - 1]
                                    if not any(x in potential_title.lower() for x in ["recent experience", "other cv snippets", "applications", "never unlocked"]):
                                        candidate_title = potential_title
                            
                            candidate_title = re.sub(r'^\d+\.\s*', '', candidate_title)
                            if candidate_title and candidate_title != "Unknown":
                                extracted_job_title = candidate_title
                                break
                except Exception as e:
                    logger.debug(f"Failed to parse job title from card text: {e}")

                 # 2. Extract Desired Role from the Desired role pane
                try:
                    desired_tab = card.locator("text='Desired role'").first
                    if await desired_tab.count() > 0:
                        await desired_tab.click(force=True)
                        await asyncio.sleep(0.4)
                        
                        # Grab the first line of the active tab pane
                        active_pane = card.locator(".tab-content .active, [class*='pane' i][class*='active' i]").first
                        if await active_pane.count() > 0:
                            pane_text = await active_pane.inner_text()
                            pane_lines = [l.strip() for l in pane_text.split("\n") if l.strip()]
                            if pane_lines:
                                extracted_desired_role = pane_lines[0]
                                # Fallback location extraction if primary location was not found
                                if len(pane_lines) > 1 and (location_text == "Unknown" or not location_text):
                                    potential_loc = pane_lines[1]
                                    if "not supplied" not in potential_loc.lower() and "not available" not in potential_loc.lower():
                                        location_text = potential_loc
                                    
                        # Fetch extra titles from +X job titles info circle tooltip
                        info_icon = card.locator("svg[class*='info' i], i[class*='info' i], [class*='info' i], a:has-text('job titles')").first
                        if await info_icon.count() > 0:
                            for attr in ["title", "aria-label", "data-tip", "data-original-title"]:
                                attr_val = await info_icon.get_attribute(attr)
                                if attr_val:
                                    extracted_desired_role += f" ({attr_val})"
                                    break
                            else:
                                await info_icon.hover(force=True)
                                await asyncio.sleep(0.5)
                                tooltip = self.page.locator(".tooltip, .popover, [role='tooltip']").first
                                if await tooltip.count() > 0 and await tooltip.is_visible():
                                    tooltip_text = await tooltip.inner_text()
                                    if tooltip_text:
                                        extracted_desired_role += f" ({tooltip_text})"
                                        
                    # Revert to Current status tab
                    curr_tab = card.locator("text='Current status'").first
                    if await curr_tab.count() > 0:
                        await curr_tab.click(force=True)
                        await asyncio.sleep(0.2)
                except Exception as e:
                    logger.debug(f"Failed to extract desired role: {e}")

                # 3. AI Pre-Screening
                is_locked = await unlock_btn.is_visible()
                if is_locked:
                    logger.info(f"Candidate {name_text} is locked. Running AI Pre-Screening on preview text...")
                    preview_text = await card.inner_text() or ""
                    pre_decision = ai_mgr.pre_classify_candidate(preview_text, name_text)
                    
                    if pre_decision.get("classification") == "UNFIT":
                        logger.info(f"Candidate {name_text} PRE-CLASSIFIED AS UNFIT. Skipping unlock to save credits. Reason: {pre_decision.get('reasoning')}")
                        
                        # Store the unfit candidate so they appear in Supabase and are tracked as processed for 30 days
                        full_data = {
                            "name": name_text,
                            "location": location_text,
                            "cv_id": cv_id,
                            "cv_link": profile_url if profile_url else "TotalJobs Search",
                            "platform_name": "TotalJobs",
                            "dcm_type": os.getenv("DCM_TYPE", "Unknown"),
                            "job_title": extracted_job_title if extracted_job_title != "Unknown" else "Unknown",
                            "desired_role": extracted_desired_role if extracted_desired_role != "Unknown" else "Unknown",
                            "classification": "UNFIT",
                            "reasoning": pre_decision.get('reasoning', "Pre-classified as unfit based on profile preview."),
                            "is_competitor_match": False,
                            "is_job_title_match": False
                        }
                        try:
                            output_mgr.append_candidate(full_data)
                            tracker.add(cv_id, "Legacy")
                            logger.info(f"Pre-screened UNFIT candidate '{name_text}' stored successfully.")
                        except Exception as e:
                            logger.error(f"Failed to store pre-screened candidate {name_text}: {e}")
                            
                        # We skip to the next candidate
                        continue
                    elif pre_decision.get("classification") == "TOKEN_ERROR":
                        logger.error("Token limit reached during pre-screening. Aborting search.")
                        return False
                    else:
                        logger.info(f"Candidate {name_text} passed pre-screening. Proceeding to unlock candidate...")

                if await unlock_btn.is_visible():
                    logger.info(f"Clicking 'Unlock candidate' for {name_text}...")
                    await unlock_btn.click(force=True)
                    await asyncio.sleep(4) # Wait for unlock to complete and UI to update
                    
                    # Close the unlocked confirmation tab/container/modal
                    logger.info("Closing unlock confirm dialog...")
                    close_selectors = [
                        "button[class*='close' i]", "a[class*='close' i]",
                        "[class*='close' i]", ".close", "button:has-text('X')", "text='X'"
                    ]
                    closed = False
                    for c_sel in close_selectors:
                        btn = self.page.locator(c_sel).filter(visible=True).first
                        if await btn.count() > 0:
                            await btn.click(force=True)
                            logger.info("Closed unlock confirm dialog.")
                            closed = True
                            await asyncio.sleep(2)
                            break
                    if not closed:
                        if len(self.page.context.pages) > 1:
                            await self.page.context.pages[-1].close()
                            logger.info("Closed newly opened tab from unlock.")
                            await asyncio.sleep(1)

                    # Reset card locator to specifically target this candidate in case it was expanded during button search
                    card = cards.nth(i)
                    
                    # 1. Re-extract Name (supports both locked text elements and unlocked anchor links)
                    name_el = card.locator("div.candidate-identifier-container .identifier, div.candidate-identifier-container a, h2, h3, a[class*='name']").first
                    name_text = "Unknown"
                    if await name_el.count() > 0:
                        name_text = await name_el.inner_text()
                        name_text = name_text.strip()
                        name_text = re.sub(r'^\d+\.\s*', '', name_text)
                        name_text = re.sub(r'\s*\(view profile\)$', '', name_text, flags=re.I)
                        name_text = name_text.strip()
                    
                    if name_text == "Unknown" or not name_text:
                        for name_sel in ["h1", "h2", "h3", "h4", "a.candidate-name", "a[class*='name' i]", "div.candidate-identifier-container a", "a"]:
                            el = card.locator(name_sel).first
                            if await el.count() > 0:
                                text = await el.inner_text()
                                text = text.strip()
                                text = re.sub(r'^\d+\.\s*', '', text)
                                text = re.sub(r'\s*\(view profile\)$', '', text, flags=re.I)
                                if text and len(text) < 60 and not any(k in text.lower() for k in ["view", "invite", "unlock", "download", "share", "email", "phone"]):
                                    name_text = text
                                    break
                                    
                    if not name_text:
                        name_text = "Unknown"

                    # 2. Re-extract Location (supports header subtitle with/without pipe, and fallback)
                    location_text = "Unknown"
                    try:
                        container_el = card.locator("div.candidate-identifier-container").first
                        if await container_el.count() > 0:
                            container_text = await container_el.inner_text() or ""
                            lines = [l.strip() for l in container_text.split("\n") if l.strip()]
                            if len(lines) >= 2:
                                # If first line is just the card number (e.g., "27."), subtitle is index 2, else index 1
                                is_number = re.match(r'^\d+\.?$', lines[0])
                                subtitle_idx = 2 if (is_number and len(lines) >= 3) else 1
                                sub_line = lines[subtitle_idx]
                                
                                if "|" in sub_line:
                                    location_text = sub_line.split("|")[-1].strip()
                                else:
                                    location_text = sub_line
                    except Exception as e:
                        logger.debug(f"Failed to parse location from header container: {e}")

                    if location_text == "Unknown" or not location_text:
                        loc_el = card.locator("div[class*='location'], span[class*='location'], div:has-text('miles')").first
                        if await loc_el.count() > 0:
                            location_text = await loc_el.inner_text()
                            location_text = location_text.replace("\n", " ").strip()
                            parts = location_text.split('|')
                            if len(parts) > 1:
                                location_text = parts[-1].strip()

                    # 3. Re-extract unique reference ID
                    profile_link_el = card.locator("a[href*='profile'], a[href*='candidate']").first
                    profile_url = ""
                    if await profile_link_el.count() > 0:
                        profile_url = await profile_link_el.get_attribute("href") or ""
                    
                    if profile_url:
                        import urllib.parse
                        id_match = re.search(r'[?&]candidateId=([^&]+)', profile_url, re.I)
                        if id_match:
                            cv_id = urllib.parse.unquote(id_match.group(1)).strip()
                        else:
                            path_match = re.search(r'(?:candidate|profile|cv)/([a-zA-Z0-9_-]+)', profile_url, re.I)
                            cv_id = path_match.group(1) if path_match else None
                    else:
                        cv_id = None
                        
                    if not cv_id:
                        cv_id = "tj_" + hashlib.md5(f"{name_text}_{location_text}".encode()).hexdigest()[:12]
                    
                    # Reconstruct profile URL
                    if cv_id and not cv_id.startswith("tj_"):
                        profile_url = f"https://recruiter.totaljobs.com/CandidateSearch/CandidateDetails.aspx?candidateId={urllib.parse.quote(cv_id)}"
                    elif profile_url and profile_url.startswith("/"):
                        profile_url = "https://recruiter.totaljobs.com" + profile_url

                    # Check if already processed (after unlocking)
                    if not force_reprocess and tracker.is_processed(cv_id, "Legacy"):
                        logger.info(f"Candidate {name_text} (ID: {cv_id}) already processed after unlock. Skipping.")
                        continue

                    # Re-locate candidate name link
                    name_link = None
                    for sel in ["div.candidate-identifier-container a", "a.candidate-name", "h2 a", "h3 a", "a[class*='name' i]", "h2", "h3"]:
                        loc = card.locator(sel).first
                        if await loc.count() > 0:
                            name_link = loc
                            break
                    if not name_link:
                        name_link = card.locator("a").first

                # Now the card shows "Invite to apply" or was just unlocked. We click to open CV.
                logger.info(f"Opening CV for {name_text}...")
                cv_text = ""
                job_title_ext = "Unknown"
                desired_role_ext = "Unknown"
                
                opened_in_new_tab = False
                if profile_url:
                    try:
                        logger.info(f"Opening candidate details directly in a new tab via URL: {profile_url}")
                        new_page = await self.page.context.new_page()
                        await new_page.goto(profile_url, wait_until="domcontentloaded")
                        # Give ample time for AJAX/API to load and render the CV text
                        await asyncio.sleep(4)
                        
                        # Click the CV tab first if it exists
                        cv_tab_selectors = ["[data-test-id='cv-tab']", "[data-testid='cv-tab']", "button:text-is('CV')", "a:text-is('CV')", "li:text-is('CV')", "div[role='tab']:text-is('CV')"]
                        for selector in cv_tab_selectors:
                            try:
                                tab = new_page.locator(selector).first
                                if await tab.is_visible(timeout=2000):
                                    await tab.click(force=True)
                                    await asyncio.sleep(1.5)
                                    break
                            except:
                                continue

                        cv_text = await new_page.inner_text("body")
                        # Extract CV text from any frame containing the CV document (CandidatePreviewCV)
                        try:
                            for frame in new_page.frames:
                                if "CandidatePreviewCV" in frame.url or "PreviewCV" in frame.url or "CandidatePreview" in frame.url:
                                    try:
                                        await frame.wait_for_selector("body", timeout=4000)
                                        iframe_text = ""
                                        for _ in range(10):
                                            iframe_text = await frame.locator("body").inner_text()
                                            if iframe_text and len(iframe_text.strip()) > 200:
                                                break
                                            await asyncio.sleep(0.5)
                                        if iframe_text and len(iframe_text.strip()) > 200:
                                            cv_text += "\n\n--- CV DOCUMENT CONTENT ---\n\n" + iframe_text
                                            logger.info("Successfully extracted CV text from CandidatePreviewCV frame.")
                                            break
                                    except Exception as frame_err:
                                        logger.debug(f"Failed to read CandidatePreviewCV frame: {frame_err}")
                        except Exception as e_frames:
                            logger.debug(f"Error checking page frames: {e_frames}")
                            
                        job_title_ext, desired_role_ext = await extract_tj_roles(new_page)
                        await new_page.close()
                        opened_in_new_tab = True
                        logger.info("Extracted CV text from direct URL in new tab.")
                    except Exception as e_direct:
                        logger.warning(f"Failed to load candidate URL directly in new tab: {e_direct}")
                        try:
                            if 'new_page' in locals() and new_page and not new_page.is_closed():
                                await new_page.close()
                                logger.info("Force-closed leaked new_page tab in except block.")
                        except: pass

                if not opened_in_new_tab and name_link and await name_link.is_visible():
                    try:
                        # Store current URL to detect navigation
                        old_url = self.page.url
                        
                        # Click the name link and check if a new page or same-page navigation occurs
                        try:
                            async with self.page.context.expect_page(timeout=4000) as new_page_info:
                                await name_link.click(force=True)
                            
                            # Case A: Opened in a new page/tab
                            new_page = await new_page_info.value
                            await new_page.wait_for_load_state("domcontentloaded")
                            await asyncio.sleep(4)
                            
                            # Click the CV tab first if it exists
                            cv_tab_selectors = ["[data-test-id='cv-tab']", "[data-testid='cv-tab']", "button:text-is('CV')", "a:text-is('CV')", "li:text-is('CV')", "div[role='tab']:text-is('CV')"]
                            for selector in cv_tab_selectors:
                                try:
                                    tab = new_page.locator(selector).first
                                    if await tab.is_visible(timeout=2000):
                                        await tab.click(force=True)
                                        await asyncio.sleep(1.5)
                                        break
                                except:
                                    continue

                            cv_text = await new_page.inner_text("body")
                            # Extract CV text from any frame containing the CV document (CandidatePreviewCV)
                            try:
                                for frame in new_page.frames:
                                    if "CandidatePreviewCV" in frame.url or "PreviewCV" in frame.url or "CandidatePreview" in frame.url:
                                        try:
                                            await frame.wait_for_selector("body", timeout=4000)
                                            iframe_text = ""
                                            for _ in range(10):
                                                iframe_text = await frame.locator("body").inner_text()
                                                if iframe_text and len(iframe_text.strip()) > 200:
                                                    break
                                                await asyncio.sleep(0.5)
                                            if iframe_text and len(iframe_text.strip()) > 200:
                                                cv_text += "\n\n--- CV DOCUMENT CONTENT ---\n\n" + iframe_text
                                                logger.info("Successfully extracted CV text from CandidatePreviewCV frame.")
                                                break
                                        except Exception as frame_err:
                                            logger.debug(f"Failed to read CandidatePreviewCV frame: {frame_err}")
                            except Exception as e_frames:
                                logger.debug(f"Error checking page frames: {e_frames}")
                                
                            job_title_ext, desired_role_ext = await extract_tj_roles(new_page)
                            await new_page.close()
                            logger.info("Extracted CV text from clicked name link in new tab.")
                        except Exception as e_case_a:
                            try:
                                if 'new_page' in locals() and new_page and not new_page.is_closed():
                                    await new_page.close()
                                    logger.info("Force-closed leaked new_page tab in Case A except block.")
                            except: pass
                            # Check if the main page navigated to a different URL (Case B)
                            await asyncio.sleep(2.5)
                            if self.page.url != old_url:
                                logger.info(f"Main page navigated to candidate profile URL: {self.page.url}. Extracting text...")
                                
                                # Click the CV tab first if it exists
                                cv_tab_selectors = ["[data-test-id='cv-tab']", "[data-testid='cv-tab']", "button:text-is('CV')", "a:text-is('CV')", "li:text-is('CV')", "div[role='tab']:text-is('CV')"]
                                for selector in cv_tab_selectors:
                                    try:
                                        tab = self.page.locator(selector).first
                                        if await tab.is_visible(timeout=2000):
                                            await tab.click(force=True)
                                            await asyncio.sleep(1.5)
                                            break
                                    except:
                                        continue

                                cv_text = await self.page.inner_text("body")
                                 # Extract CV text from any frame containing the CV document (CandidatePreviewCV)
                                try:
                                    for frame in self.page.frames:
                                        if "CandidatePreviewCV" in frame.url or "PreviewCV" in frame.url or "CandidatePreview" in frame.url:
                                            try:
                                                await frame.wait_for_selector("body", timeout=4000)
                                                iframe_text = ""
                                                for _ in range(10):
                                                    iframe_text = await frame.locator("body").inner_text()
                                                    if iframe_text and len(iframe_text.strip()) > 200:
                                                        break
                                                    await asyncio.sleep(0.5)
                                                if iframe_text and len(iframe_text.strip()) > 200:
                                                    cv_text += "\n\n--- CV DOCUMENT CONTENT ---\n\n" + iframe_text
                                                    logger.info("Successfully extracted CV text from CandidatePreviewCV frame in Case B.")
                                                    break
                                            except Exception as frame_err:
                                                logger.debug(f"Failed to read CandidatePreviewCV frame: {frame_err}")
                                except Exception as e_frames:
                                    logger.debug(f"Error checking page frames: {e_frames}")
                                    
                                job_title_ext, desired_role_ext = await extract_tj_roles(self.page)
                                # Go back to the search results
                                logger.info("Navigating back to search results...")
                                await self.page.go_back(wait_until="domcontentloaded")
                                await asyncio.sleep(2.5)
                            else:
                                # Case C: Opened in a modal/dialog on the same page
                                logger.info("No new tab or page navigation. Checking for visible CV modal overlay...")
                                modal = None
                                # Modals in TotalJobs can be matched by standard classes or overlays
                                for modal_sel in [
                                    ".modal-content",
                                    "[role='dialog']",
                                    ".dialog",
                                    ".viewer",
                                    ".cv-viewer",
                                    "[class*='modal' i]",
                                    "[class*='viewer' i]",
                                    "[class*='popup' i]"
                                ]:
                                    loc = self.page.locator(modal_sel).filter(visible=True).first
                                    if await loc.count() > 0:
                                        modal = loc
                                        break
                                
                                if modal:
                                    logger.info("Visible modal/dialog found. Extracting text...")
                                    cv_text = await modal.inner_text()
                                    # Extract CV text from any frame containing the CV document (CandidatePreviewCV)
                                    try:
                                        for frame in self.page.frames:
                                            if "CandidatePreviewCV" in frame.url or "PreviewCV" in frame.url or "CandidatePreview" in frame.url:
                                                try:
                                                    await frame.wait_for_selector("body", timeout=4000)
                                                    iframe_text = ""
                                                    for _ in range(10):
                                                        iframe_text = await frame.locator("body").inner_text()
                                                        if iframe_text and len(iframe_text.strip()) > 200:
                                                            break
                                                        await asyncio.sleep(0.5)
                                                    if iframe_text and len(iframe_text.strip()) > 200:
                                                        cv_text += "\n\n--- CV DOCUMENT CONTENT ---\n\n" + iframe_text
                                                        logger.info("Successfully extracted CV text from CandidatePreviewCV frame in Case C.")
                                                        break
                                                except Exception as frame_err:
                                                    logger.debug(f"Failed to read CandidatePreviewCV frame: {frame_err}")
                                    except Exception as e_frames:
                                        logger.debug(f"Error checking page frames: {e_frames}")
                                        
                                    job_title_ext, desired_role_ext = await extract_tj_roles(modal)
                                    
                                    # Close the modal
                                    logger.info("Closing CV modal...")
                                    close_btn = modal.locator("button[class*='close' i], a[class*='close' i], button[aria-label*='close' i], [class*='close' i], .close, button:has-text('X')").first
                                    if await close_btn.count() == 0:
                                        close_btn = self.page.locator(".modal-content button.close, .dialog button.close, [class*='close' i]").filter(visible=True).first
                                        
                                    if await close_btn.count() > 0:
                                        await close_btn.click(force=True)
                                        await asyncio.sleep(2)
                                else:
                                    logger.warning("No visible CV modal found.")
                    except Exception as e:
                        logger.error(f"Error opening CV: {e}")
                
                # 6. Parse and classify CV
                if cv_text and len(cv_text.strip()) > 100:
                    work_done = True
                    logger.info(f"Extracted {len(cv_text)} chars of CV. Classifying...")
                    ai_result = ai_mgr.classify_candidate(cv_text, expected_name=name_text)
                    
                    classification = ai_result.get("classification")
                    if classification in ["ERROR", "TOKEN_ERROR"]:
                        error_msg = ai_result.get("reasoning", "").lower()
                        error_type = ai_result.get("error_type")
                        is_token_limit = (classification == "TOKEN_ERROR" or 
                                          error_type == "TOKEN_LIMIT" or 
                                          any(x in error_msg for x in ["insufficient_quota", "balance", "quota", "billing", "limit", "429", "402", "credit", "token"]))
                        
                        if is_token_limit:
                            logger.error("AI API limit or balance reached. Stopping processing to prevent skipping CVs.")
                            import discord_alert; discord_alert.pause_and_alert() # Auto-Resume added

                        logger.error(f"AI error for CV {cv_id}. Skipping and NOT adding to processed tracker.")
                        continue
                    
                    # Extract job_title and desired_role roughly from card text if needed, 
                    # or leave as "Unknown" for now since TotalJobs format differs from CV-Library
                    
                    full_data = {
                        "name": name_text if name_text != "Unknown" else ai_result.get("candidate_name", "Unknown"),
                        "location": location_text if location_text != "Unknown" else ai_result.get("location", "Unknown"),
                        "cv_id": cv_id,
                        "cv_link": profile_url if profile_url else "TotalJobs Search",
                        "platform_name": "TotalJobs",
                        "dcm_type": os.getenv("DCM_TYPE", "Unknown"),
                        "job_title": job_title_ext if job_title_ext != "Unknown" else ai_result.get("current_position", "Unknown"),
                        "desired_role": desired_role_ext if desired_role_ext != "Unknown" else ai_result.get("desired_role", "Unknown")
                    }
                    full_data = {**full_data, **ai_result}
                    
                    # Save to Google Sheets
                    output_mgr.append_candidate(full_data)
                    
                    # Track as processed
                    tracker.add(cv_id, "Legacy")
                    import random
                    sleep_time = random.uniform(4, 5)
                    logger.info(f"Waiting {sleep_time:.2f} seconds before processing next CV...")
                    await asyncio.sleep(sleep_time)
                else:
                    logger.warning(f"Could not extract meaningful CV text for candidate: {name_text}")
                    
            except Exception as e:
                logger.error(f"Error processing candidate card {i}: {e}")
                
        return work_done


