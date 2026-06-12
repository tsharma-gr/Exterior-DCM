import asyncio
from logger_config import logger
from playwright.async_api import Page
import re

class OutlookReader:
    def __init__(self, page: Page):
        self.page = page
        self.url = "https://outlook.office.com/mail/"

    async def navigate_to_inbox(self):
        """Navigates to Outlook Web and opens the target folder."""
        current_url = self.page.url
        if not ("outlook" in current_url and "/mail" in current_url):
            logger.info("Navigating to Outlook Web...")
            await self.page.goto(self.url, wait_until="domcontentloaded")
            await self.page.wait_for_selector('div[role="main"]', timeout=30000)
            logger.info("Outlook Web loaded.")
            await asyncio.sleep(3) # Give sidebar time to render
            
        target_folder = "Exterior Alerts"
        logger.info(f"Navigating to subfolder: {target_folder}")
        try:
            # Look for the folder in the sidebar by exact text match
            folder_locator = self.page.locator(f'span:text-is("{target_folder}")')
            if await folder_locator.count() > 0:
                await folder_locator.first.click()
                logger.info(f"Successfully selected '{target_folder}'.")
                await asyncio.sleep(2) # Give emails time to load
            else:
                # Outlook sometimes uses titles or inner text differently
                folder_alt = self.page.locator(f'[title="{target_folder}"]')
                if await folder_alt.count() > 0:
                    await folder_alt.first.click()
                    logger.info(f"Successfully selected '{target_folder}' via title attribute.")
                    await asyncio.sleep(2)
                else:
                    logger.warning(f"Could not find '{target_folder}' folder in the sidebar. Please make sure it is visible.")
        except Exception as e:
            logger.error(f"Error selecting folder: {e}")

    async def process_emails_one_by_one(self, cv_parser, ai_mgr, tracker, criteria_text, output_mgr):
        logger.info("Initializing Bottom-to-Top Scan (Oldest First)...")
        await asyncio.sleep(2)
        
        # 1. Capture the ID of the TOP email so we know when to stop
        messages = self.page.locator('div[aria-label="Message list"] div[role="option"]')
        if await messages.count() == 0:
            logger.info("No emails found in Inbox.")
            return False
            
        top_text = await messages.first.inner_text()
        top_id = top_text[:100]
        logger.info(f"Top email marker captured: {top_id[:30]}...")

        # 2. FIND STARTING POINT (Oldest Unprocessed Email)
        logger.info("Searching for the oldest unprocessed email (downward search)...")
        await messages.first.click()
        await asyncio.sleep(1.5)
        
        last_id = None
        stuck_count = 0
        recovery_count = 0
        boundary_found = False
        search_depth = 0
        
        while not boundary_found:
            search_depth += 1
            current_selected = self.page.locator('div[aria-label="Message list"] div[aria-selected="true"]').first
            if await current_selected.count() == 0:
                logger.info("No email selected. Pressing End to skip...")
                await self.page.keyboard.press("End")
                await asyncio.sleep(0.5)
                continue
                
            text = await current_selected.inner_text()
            current_id = text[:100]
            
            # Stuck detection (reached bottom of inbox)
            if current_id == last_id:
                stuck_count += 1
                if stuck_count >= 3:
                    recovery_count += 1
                    if recovery_count >= 3:
                        logger.info("Reached absolute bottom of inbox during downward search.")
                        break
                    
                    logger.info("Navigation stuck during downward search. Attempting scrolling recovery...")
                    await self.page.mouse.wheel(0, 800)
                    await asyncio.sleep(0.5)
                    await self.page.keyboard.press("End")
                    stuck_count = 0
                    continue
            else:
                stuck_count = 0
                last_id = current_id
                recovery_count = 0
            
            # Forced downward traversal - no early exit
            # We skip checking read/unread or processed status here
            # to forcefully reach the absolute bottom of the inbox.
            
            # Move Down instantly by pressing End instead of ArrowDown
            await self.page.keyboard.press("End")
            await asyncio.sleep(0.3)
            
        logger.info("Boundary search complete. Starting upward processing...")

        # 3. NAVIGATE UPWARDS UNTIL WE REACH THE TOP MARKER
        work_done = False
        last_item_id = None
        stuck_count = 0
        last_cv_link = None
        
        while True:
            try:
                selected_item = self.page.locator('div[aria-label="Message list"] div[aria-selected="true"]').first
                if await selected_item.count() == 0: 
                    await self.page.keyboard.press("ArrowUp")
                    await asyncio.sleep(0.5)
                    continue
                
                text = await selected_item.inner_text()
                current_item_id = text[:100]
                
                # STUCK DETECTION
                if current_item_id == last_item_id:
                    stuck_count += 1
                    if stuck_count >= 4:
                        logger.warning("Navigation stuck on same email for 4 attempts. Trying to safely force up...")
                        await self.page.keyboard.press("ArrowUp")
                        await asyncio.sleep(1.0)
                        stuck_count = 0
                        continue
                else:
                    stuck_count = 0
                    last_item_id = current_item_id

                if "CV Watchdog Alert" in text and "Exterior" in text:
                    # --- NEW: Extract and SANITIZE name directly from the message list ---
                    raw_lines = [line.strip() for line in text.split("\n") if line.strip()]
                    list_name = raw_lines[0] if raw_lines else "Unknown"
                    
                    # Remove Outlook Icons (non-printable/special characters)
                    import re
                    list_name = re.sub(r'[^\x20-\x7E]+', '', list_name).strip() 
                    # Clean up common noise
                    list_name = list_name.replace("CV-Library", "").replace("CV Watchdog", "").strip()

                    # --- CRITICAL FIX: CLICK AND VERIFY SYNC ---
                    await selected_item.click()
                    
                    # Smart dynamic sync for upward scan
                    await asyncio.sleep(0.8)
                    email_data = await self._extract_current_email_data()
                    
                    # --- VERIFY NAME SYNC ---
                    if email_data and list_name.lower() not in email_data.get("name", "").lower():
                        logger.warning(f"Sync mismatch: List='{list_name}' vs ReadingPane='{email_data.get('name')}'. Retrying...")
                        await asyncio.sleep(1.5)
                        email_data = await self._extract_current_email_data()

                    if email_data and email_data.get("cv_id"):
                        if not tracker.is_processed(email_data["cv_id"]):
                            work_done = True
                            last_cv_link = email_data.get("cv_link")
                            # Override name with list_name if it's more accurate
                            if list_name and len(list_name) > 3:
                                email_data["name"] = list_name
                            email_data["platform_name"] = "CV-Library"
                                
                            logger.info(f"Processing candidate: {email_data.get('name')} (ID: {email_data['cv_id']})")
                            await self._process_single_candidate_v2(selected_item, email_data, cv_parser, ai_mgr, tracker, criteria_text, output_mgr)
                        else:
                            logger.info(f"Skipping {email_data.get('name')} - CV ID {email_data['cv_id']} is already in processed list.")
                
                # Check if we are back at the top
                if current_item_id == top_id:
                    logger.info("Reached the top of the inbox marker. Cycle complete.")
                    break
                    
                # Move Up safely
                await self.page.keyboard.press("ArrowUp")
                await asyncio.sleep(0.5) # Increased sleep to prevent skipping
                
            except Exception as e:
                logger.error(f"Error during upward navigation: {e}")
                await self.page.keyboard.press("ArrowUp")
                await asyncio.sleep(1.0)
        
        return work_done

    async def process_emails_top_to_bottom(self, cv_parser, ai_mgr, tracker, criteria_text, output_mgr):
        logger.info("Initializing Smart Scan (Fast Down -> Process Up)...")
        await asyncio.sleep(2)
        
        messages = self.page.locator('div[aria-label="Message list"] div[role="option"]')
        if await messages.count() == 0:
            logger.info("No emails found in Inbox.")
            return False
            
        # 1. Start at the top email
        await messages.first.click()
        await asyncio.sleep(1.5)
        
        top_text = await messages.first.inner_text()
        top_id = top_text[:100]
        
        last_item_id = None
        stuck_count = 0
        boundary_found = False
        
        logger.info("PHASE 1: Fast scanning downwards to find the processed boundary...")
        
        while not boundary_found:
            try:
                selected_item = self.page.locator('div[aria-label="Message list"] div[aria-selected="true"]').first
                if await selected_item.count() == 0: 
                    await self.page.keyboard.press("ArrowDown")
                    await asyncio.sleep(0.3)
                    continue
                
                text = await selected_item.inner_text()
                current_item_id = text[:100]
                
                # STUCK DETECTION / REACHED BOTTOM
                if current_item_id == last_item_id:
                    stuck_count += 1
                    if stuck_count >= 4:
                        logger.info("Reached absolute bottom of inbox.")
                        boundary_found = True
                        break
                else:
                    stuck_count = 0
                    last_item_id = current_item_id

                # Check if unread (Outlook includes 'Unread' in aria-label for unread messages)
                aria_label = await selected_item.get_attribute("aria-label")
                is_unread = aria_label and "Unread" in aria_label
                
                if is_unread:
                    # "if mail is unread so come faslty to bottm"
                    await self.page.keyboard.press("ArrowDown")
                    await asyncio.sleep(0.2)
                    continue

                if "CV Watchdog Alert" in text and "Exterior" in text:
                    # Mail is READ. Let's check ID to see if it's our boundary.
                    await selected_item.click()
                    await asyncio.sleep(0.8)
                    email_data = await self._extract_current_email_data(list_item_text=text)
                    
                    if email_data and email_data.get("cv_id"):
                        if tracker.is_processed(email_data["cv_id"]):
                            logger.info(f"Boundary Found! Hit already processed CV ID: {email_data['cv_id']}")
                            boundary_found = True
                            break
                
                # If read but not processed, keep going down
                if not boundary_found:
                    await self.page.keyboard.press("ArrowDown")
                    await asyncio.sleep(0.3)
                    
            except Exception as e:
                logger.error(f"Error during fast downward scan: {e}")
                await self.page.keyboard.press("ArrowDown")
                await asyncio.sleep(0.5)
                
        logger.info("PHASE 2: Reversing direction. Processing upwards...")
        
        work_done = False
        last_up_id = None
        stuck_up_count = 0
        
        while True:
            try:
                # Move up first to step off the boundary email
                await self.page.keyboard.press("ArrowUp")
                await asyncio.sleep(0.5)
                
                selected_item = self.page.locator('div[aria-label="Message list"] div[aria-selected="true"]').first
                if await selected_item.count() == 0: continue
                
                text = await selected_item.inner_text()
                current_item_id = text[:100]
                
                if current_item_id == last_up_id:
                    stuck_up_count += 1
                    if stuck_up_count >= 4:
                        logger.info("Reached top of inbox (stuck check). Cycle complete.")
                        break
                else:
                    stuck_up_count = 0
                    last_up_id = current_item_id
                    
                if "CV Watchdog Alert" in text and "Exterior" in text:
                    raw_lines = [line.strip() for line in text.split("\n") if line.strip()]
                    list_name = raw_lines[0] if raw_lines else "Unknown"
                    import re
                    list_name = re.sub(r'[^\x20-\x7E]+', '', list_name).strip() 
                    list_name = list_name.replace("CV-Library", "").replace("CV Watchdog", "").strip()

                    await selected_item.click()
                    await asyncio.sleep(0.8)
                    email_data = await self._extract_current_email_data(list_item_text=text)
                    
                    # --- VERIFY NAME SYNC ---
                    if email_data and list_name.lower() not in email_data.get("name", "").lower():
                        logger.warning(f"Sync mismatch: List='{list_name}' vs ReadingPane='{email_data.get('name')}'. Retrying...")
                        await asyncio.sleep(1.5)
                        email_data = await self._extract_current_email_data(list_item_text=text)
                    
                    if email_data and email_data.get("cv_id") and not tracker.is_processed(email_data["cv_id"]):
                        work_done = True
                        if list_name and len(list_name) > 3:
                            email_data["name"] = list_name
                            
                        logger.info(f"Processing candidate: {email_data.get('name')} (ID: {email_data['cv_id']})")
                        await self._process_single_candidate_v2(selected_item, email_data, cv_parser, ai_mgr, tracker, criteria_text, output_mgr)
                        
                if current_item_id == top_id:
                    logger.info("Reached the original top marker. Cycle complete.")
                    break
                    
            except Exception as e:
                logger.error(f"Error during upward processing: {e}")
                await self.page.keyboard.press("ArrowUp")
                await asyncio.sleep(1.0)
        
        return work_done

    async def _process_single_candidate_v2(self, item, email_data, cv_parser, ai_mgr, tracker, criteria_text, output_mgr):
        """Modified helper that assumes email is already selected and loaded."""
        cv_text = await cv_parser.extract_cv_text(email_data["cv_link"])
        if cv_text:
            ai_result = ai_mgr.classify_candidate(cv_text, criteria_text, expected_name=email_data.get("name"))
            full_data = {**email_data, **ai_result}
            output_mgr.append_candidate(full_data)
            tracker.add(email_data["cv_id"])
            await self.mark_as_read()

    async def _process_single_candidate(self, item, email_data, cv_parser, ai_mgr, tracker, criteria_text, output_mgr):
        """Helper to handle the actual CV processing logic."""
        await item.click()
        # Wait longer for the reading pane to update
        await asyncio.sleep(2) 
        
        cv_text = await cv_parser.extract_cv_text(email_data["cv_link"])
        if cv_text:
            ai_result = ai_mgr.classify_candidate(cv_text, criteria_text)
            # AI's extracted name should be the master source of truth
            full_data = {**email_data, **ai_result}
            output_mgr.append_candidate(full_data)
            tracker.add(email_data["cv_id"])
            await self.mark_as_read()

    async def _extract_current_email_data(self, list_item_text=None):
        """Extracts data from the currently selected email in the reading pane and the list item text."""
        # Wait for the reading pane to load content
        reading_pane_selector = 'div[role="main"]'
        await self.page.wait_for_selector(reading_pane_selector, timeout=10000)
        
        reading_pane = await self.page.query_selector(reading_pane_selector)
        if not reading_pane:
            return None
        
        content = await reading_pane.inner_text()
        
        # If "No preview" or empty, wait a bit more
        if "No preview" in content or len(content.strip()) < 50:
            await asyncio.sleep(2)
            content = await reading_pane.inner_text()

        data = {
            "name": self._extract_field(content, r"Name[:\s]+(.*)"),
            "current_title": self._extract_field(content, r"(?:Current Job Title|Job Title)[:\s]+(.*)"),
            "match_percentage": self._extract_field(content, r"Match Percentage[:\s]+(\d+%)"),
            "desired_industry": self._extract_field(content, r"Desired Industry[:\s]+(.*)"),
            "expected_salary": self._extract_field(content, r"Expected Salary[:\s]+(.*)"),
            "location": self._extract_field(content, r"Location[:\s]+(.*)"),
            "relocation": self._extract_field(content, r"Relocation Status[:\s]+(.*)"),
            "cv_link": await self._extract_cv_link(),
        data["platform_name"] = "Outlook"
        
        # Fallback for Name if still N/A
        if data["name"] == "N/A":
            # Try to get it from the header/subject area
            subject_area = await self.page.inner_text('div[role="main"]') # Re-check main content
            match = re.search(r"Name:\s*([^,\n\r]*)", subject_area)
            if match:
                data["name"] = match.group(1).strip()

        if data["cv_link"]:
            ref_match = re.search(r"cv/(\d+)", data["cv_link"])
            data["cv_id"] = ref_match.group(1) if ref_match else data["cv_link"]
        else:
            data["cv_id"] = None
            
        return data

    def _extract_field(self, text, pattern):
        # Use DOTALL to handle potential multi-line values if needed, 
        # but usually we just want the rest of the line
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = match.group(1).strip()
            # Clean up common Outlook noise
            val = val.split('\n')[0] # Only take the first line
            val = val.replace(')', '').replace('(', '').strip()
            return val
        return "N/A"

    async def _extract_cv_link(self):
        # Look for links containing cv-library.co.uk
        # Outlook links can be wrapped in tracking URLs
        links = await self.page.query_selector_all('a[href*="cv-library.co.uk"]')
        for link in links:
            href = await link.get_attribute("href")
            if "cv/" in href or "view-cv" in href:
                return href
        return None

    async def mark_as_read(self):
        # Implementation to mark as read or move to folder
        # Right click -> Mark as read or use keyboard shortcut 'Q'
        await self.page.keyboard.press("q")
        logger.info("Email marked as read.")
