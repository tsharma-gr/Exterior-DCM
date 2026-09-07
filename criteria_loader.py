import os
import json
import sys
from logger_config import logger

class CriteriaLoader:
    def __init__(self, filepath=None):
        self.filepath = filepath or r"D:\TalentVerse AI\Automation Tool\Guide\guide.json"

    def load_criteria(self):
        """Loads and validates the JSON guide file."""
        if not os.path.exists(self.filepath):
            logger.critical(f"[STARTUP] guide.json NOT FOUND at {self.filepath}")
            sys.exit(1)
            
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = f.read().strip()
                if not data:
                    logger.critical("[STARTUP] guide.json is EMPTY.")
                    sys.exit(1)
                    
                criteria = json.loads(data)
                
                # Basic validation of required keys
                required_keys = ["scoring_weights", "classification_thresholds", "red_flags_exclude"]
                for key in required_keys:
                    if key not in criteria:
                        logger.critical(f"[STARTUP] guide.json is INVALID: Missing key '{key}'")
                        sys.exit(1)
                
                logger.info("[STARTUP] guide.json loaded and validated successfully.")
                return criteria
        except json.JSONDecodeError as e:
            logger.critical(f"[STARTUP] guide.json CORRUPTED: {e}")
            sys.exit(1)
        except Exception as e:
            logger.critical(f"[STARTUP] Unexpected error loading guide.json: {e}")
            sys.exit(1)
