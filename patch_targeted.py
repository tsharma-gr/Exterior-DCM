import re
import os

TASK_2_PATH = r"D:\TalentVerse AI\GitHub\Task 2(Exterior DCM)\Automation Tool(Exterior-CV Library)\cv_automation\totaljobs_searcher.py"
TASK_4_PATH = r"D:\TalentVerse AI\GitHub\Task 4(Structural DCM)\Automation Tool(Structural-CV Libraray)\cv_automation\totaljobs_searcher.py"

TARGETED_LOGIC = """            logger.info("Parsing boolean keywords...")
            # Split keywords by " AND " (case-insensitive)
            import re
            parts = re.split(r'\\s+AND\\s+', boolean_keywords, maxsplit=1, flags=re.IGNORECASE)
            cv_keywords = parts[0].strip() if len(parts) > 0 else boolean_keywords
            job_title_keywords = parts[1].strip() if len(parts) > 1 else ""

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

"""

def patch_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r'            logger\.info\("Filling \'Search anything in CV or Profile\'\.\.\."\).*?(?=            logger\.info\("Filling Location \'UK\'\.\.\."\))'
    
    match = re.search(pattern, content, flags=re.DOTALL)
    if not match:
        print(f"Could not find pattern in {filepath}")
        return
        
    new_content = content.replace(match.group(0), TARGETED_LOGIC)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Patched {filepath}")

patch_file(TASK_2_PATH)
patch_file(TASK_4_PATH)
