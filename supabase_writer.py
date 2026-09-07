import os
import re
from supabase import create_client, Client
from logger_config import logger
from dotenv import load_dotenv

load_dotenv()

# Terminal Colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


class SupabaseWriter:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        self.table_name = os.getenv("SUPABASE_TABLE", "candidates")
        self.client = None
        self._authenticate()

    def _authenticate(self):
        try:
            if not self.url or not self.key:
                logger.error(
                    "SUPABASE_URL or SUPABASE_KEY is missing in .env!"
                )
                return

            # Remove /rest/v1/ if accidentally added
            clean_url = self.url.replace("/rest/v1/", "").strip()

            if clean_url.endswith("/"):
                clean_url = clean_url[:-1]

            self.client: Client = create_client(
                clean_url,
                self.key
            )

            logger.info(
                f"{GREEN}Successfully connected to Supabase.{RESET}"
            )

        except Exception as e:
            logger.error(
                f"{RED}Supabase Connection Error: {str(e)}{RESET}"
            )

    def append_candidate(self, data):
        """
        Insert candidate record into Supabase candidates table.
        """

        if not self.client:
            logger.error(
                "Cannot append candidate: Supabase connection not established."
            )
            return None

        try:
            sal = data.get("salary_range", None)
            if isinstance(sal, str):
                sal = re.sub(r'\s+to\s+', ' - ', sal, flags=re.I)
                sal = re.sub(r'\s*(?:per\s+annum|per\s+year|p\.a\.|pa)\b', '', sal, flags=re.I)
                sal = sal.strip()

            name_val = data.get("name", "N/A")
            title_val = data.get("job_title", "Unknown")
            if name_val in ["Unknown", "N/A"] and title_val in ["Unknown", "N/A"]:
                logger.info(f"Skipping Supabase insert: Candidate has both Unknown Name and Unknown Title.")
                return None
                
            row = {
                "candidate_name": name_val,
                "classification": data.get("classification", "N/A"),
                "ai_reasoning": data.get("reasoning", "N/A"),
                "current_position": data.get("current_position", "N/A"),
                "job_title": data.get("job_title", "Unknown"),
                "desired_role": data.get("desired_role", "Unknown"),
                "location": data.get("location", "N/A"),
                "cv_reference": data.get("cv_id", "N/A"),
                "cv_link": data.get("cv_link", "N/A"),
                "platform_name": data.get("platform_name", "N/A"),
                "dcm_type": data.get("dcm_type", "Unknown"),
                "email": data.get("email", None),
                "phone_number": data.get("phone_number", None),
                "linkedin_url": data.get("linkedin_url", None),
                "salary_range": sal,
                "t1_tenure": data.get("t1_tenure", None),
                "t2_tenure": data.get("t2_tenure", None),
                "business_specialization": data.get("business_specialization", None),
                "current_company": data.get("current_company", "N/A"),
            }

            response = (
                self.client
                .table(self.table_name)
                .insert(row)
                .execute()
            )

            logger.info(
                f"{GREEN}Candidate '{data.get('name', 'Unknown')}' "
                f"stored in Supabase successfully.{RESET}"
            )

            return response

        except Exception as e:
            logger.error(
                f"{RED}Error writing candidate to Supabase: {str(e)}{RESET}"
            )
            return None

    def update_bot_status(self, status: str):
        """
        Upsert the bot's current status into the bot_status table.
        """
        if not self.client:
            return None
            
        dcm_type = os.getenv("DCM_TYPE", "Unknown")
        
        try:
            from datetime import datetime, timezone
            row = {
                "dcm_type": dcm_type,
                "status": status,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
            response = (
                self.client
                .table("bot_status")
                .upsert(row)
                .execute()
            )
            
            logger.info(f"{GREEN}Successfully updated bot status to {status} for {dcm_type}.{RESET}")
            return response
            
        except Exception as e:
            logger.error(f"{RED}Error updating bot status in Supabase: {str(e)}{RESET}")
            return None