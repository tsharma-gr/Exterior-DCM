import os
import json
import sys
from logger_config import logger

class CriteriaLoader:
    def __init__(self, filepath=None):
        self.filepath = filepath or r"D:\TalentVerse AI\Automation Tool\Guide\guide.json"

    def load_criteria(self):
        """Loads and validates the JSON guide file."""
        # OBSOLETE: The AI rules are now fully hardcoded into ai_classifier.py.
        # We return an empty dict here so the program doesn't crash on the manager's PC
        # if the old guide.json file is missing.
        return {}
