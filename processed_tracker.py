import json
import os
from datetime import datetime, timedelta
from logger_config import logger

class ProcessedTracker:
    def __init__(self, filename="processed_cvs.json"):
        self.filename = filename
        self.processed_data = self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        # Convert legacy list to dictionary format
                        now_str = datetime.now().isoformat()
                        return {str(k): {"processed_date": now_str, "update_str": "Legacy"} for k in data}
                    return data
            except Exception as e:
                logger.error(f"Error loading processed CVs: {e}")
                return {}
        return {}

    def is_processed(self, cv_id, current_update_str=None):
        cv_id = str(cv_id)
        if cv_id not in self.processed_data:
            return False
            
        # Check "Last Viewed" date extracted from CV-Library website
        # current_update_str should be "DD/MM/YYYY"
        if current_update_str and current_update_str != "Legacy":
            try:
                last_viewed_date = datetime.strptime(current_update_str, "%d/%m/%Y")
                if datetime.now() - last_viewed_date > timedelta(days=30):
                    logger.info(f"CV {cv_id} was Last Viewed on CV-Library > 1 month ago ({current_update_str}). Re-processing!")
                    return False
            except Exception as e:
                logger.error(f"Error parsing Last Viewed date '{current_update_str}': {e}")
                
        return True # Already processed and viewed within 30 days

    def add(self, cv_id, update_str="Legacy"):
        self.processed_data[str(cv_id)] = {
            "processed_date": datetime.now().isoformat(),
            "update_str": update_str
        }
        self._save()

    def _save(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.processed_data, f)
        except Exception as e:
            logger.error(f"Error saving processed CVs: {e}")
