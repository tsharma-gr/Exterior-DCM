import json
import os
from logger_config import logger

class ProcessedTracker:
    def __init__(self, filename="processed_cvs.json"):
        self.filename = filename
        self.processed_ids = self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    return set(json.load(f))
            except Exception as e:
                logger.error(f"Error loading processed CVs: {e}")
                return set()
        return set()

    def is_processed(self, cv_id):
        return cv_id in self.processed_ids

    def add(self, cv_id):
        self.processed_ids.add(cv_id)
        self._save()

    def _save(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(list(self.processed_ids), f)
        except Exception as e:
            logger.error(f"Error saving processed CVs: {e}")
