import os
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
            row = {
                "candidate_name": data.get("name", "N/A"),
                "classification": data.get("classification", "N/A"),
                "ai_reasoning": data.get("reasoning", "N/A"),
                "current_position": data.get("current_position", "N/A"),
                "location": data.get("location", "N/A"),
                "cv_reference": data.get("cv_id", "N/A"),
                "cv_link": data.get("cv_link", "N/A"),
                "platform_name": data.get("platform_name", "N/A"),
                "dcm_type": data.get("dcm_type", "Exterior")
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