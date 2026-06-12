import pandas as pd
import os
import pytz
from datetime import datetime
from logger_config import logger

class ExcelWriter:
    def __init__(self, filepath="data/shortlisted_candidates.xlsx"):
        self.filepath = filepath
        self.columns = [
            'Candidate Name', 'Classification', 'AI Reasoning', 
            'CV Current Position', 'Location', 
            'CV Reference ID', 'CV Link', 'Processed Timestamp'
        ]
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        if not os.path.exists(os.path.dirname(self.filepath)):
            os.makedirs(os.path.dirname(self.filepath))
        
        if not os.path.exists(self.filepath):
            df = pd.DataFrame(columns=self.columns)
            df.to_excel(self.filepath, index=False)
            logger.info(f"Created new Excel file at {self.filepath}")

    def append_candidate(self, data):
        try:
            # Get current time in UK timezone (London)
            uk_tz = pytz.timezone('Europe/London')
            uk_time = datetime.now(uk_tz).strftime("%Y-%m-%d %H:%M:%S")

            # Prepare data row
            row = {
                "Candidate Name": data.get("name"),
                "Classification": data.get("classification"),
                "AI Reasoning": data.get("reasoning"),
                "CV Current Position": data.get("current_position", data.get("current_title")),
                "Location": data.get("location"),
                "CV Reference ID": data.get("cv_id"),
                "CV Link": data.get("cv_link"),
                "Processed Timestamp": uk_time
            }
            
            # Read existing, append, and save
            df = pd.read_excel(self.filepath)
            df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
            df.to_excel(self.filepath, index=False)
            logger.info(f"Appended candidate {data.get('name')} to Excel (UK Time).")
        except Exception as e:
            logger.error(f"Error writing to Excel: {e}")
