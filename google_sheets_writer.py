import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import pytz
import os
from logger_config import logger
from dotenv import load_dotenv

load_dotenv()

# UI Colors for terminal
GREEN = "\033[92m"
RESET = "\033[0m"

class GoogleSheetsWriter:
    def __init__(self):
        self.scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Paths and config
        self.key_file = os.getenv("GOOGLE_SHEETS_KEY_FILE", "google_keys.json")
        self.sheet_url = os.getenv("GOOGLE_SHEET_URL")
        
        self.columns = [
            'Candidate Name', 'Classification', 'AI Reasoning', 
            'CV Current Position', 'Location', 
            'CV Reference ID', 'CV Link', 'Processed Timestamp',
            'Alert Received Time'
        ]
        
        self.client = None
        self.sheet = None
        self._authenticate()

    def _authenticate(self):
        try:
            if not os.path.exists(self.key_file):
                logger.error(f"Google Key file NOT FOUND at: {os.path.abspath(self.key_file)}")
                return

            if not self.sheet_url or "YOUR_GOOGLE_SHEET_URL_HERE" in self.sheet_url:
                logger.error("GOOGLE_SHEET_URL is missing or still set to placeholder in .env!")
                return

            creds = Credentials.from_service_account_file(self.key_file, scopes=self.scope)
            self.client = gspread.authorize(creds)
            
            # Open by URL
            spreadsheet = self.client.open_by_url(self.sheet_url)
            self.sheet = spreadsheet.get_worksheet(0)
            
            # Ensure headers
            existing_headers = self.sheet.row_values(1)
            if not existing_headers:
                self.sheet.append_row(self.columns)
                logger.info("Initialized Google Sheet with headers.")
            
            logger.info(f"{GREEN}Successfully connected to Google Sheet: {spreadsheet.title}{RESET}")
        except Exception:
            import traceback
            logger.error(f"Google Sheets Connection Error Detail:\n{traceback.format_exc()}")
            logger.error("Please ensure you have shared the sheet with the email in your JSON key file.")

    def append_candidate(self, data):
        if not self.sheet:
            logger.error("Cannot append candidate: Google Sheet connection not established.")
            return

        try:
            # Get current time in UK timezone (London)
            uk_tz = pytz.timezone('Europe/London')
            uk_time = datetime.now(uk_tz).strftime("%Y-%m-%d %H:%M:%S")

            # Prepare data row in correct order
            row = [
                data.get("name", "N/A"),
                data.get("classification", "N/A"),
                data.get("reasoning", "N/A"),
                data.get("current_position", "N/A"),
                data.get("location", "N/A"),
                data.get("cv_id", "N/A"),
                data.get("cv_link", "N/A"),
                uk_time,
                data.get("alert_received_time", "N/A")
            ]
            # Bypass append_row filter bug by finding the exact next empty row
            col_values = self.sheet.col_values(1)
            next_row = len(col_values) + 1
            
            # Use insert_row at the calculated index instead of append_row
            self.sheet.insert_row(row, index=next_row, value_input_option='USER_ENTERED')
            logger.info(f"Appended candidate {data.get('name')} to Google Sheets (Row {next_row}, UK Time).")
        except Exception as e:
            logger.error(f"Error writing to Google Sheets: {e}")
