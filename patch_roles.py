import re
import os

TASK_2_DIR = r"D:\TalentVerse AI\GitHub\Task 2(Exterior DCM)\Automation Tool(Exterior-CV Library)\cv_automation"
TASK_4_DIR = r"D:\TalentVerse AI\GitHub\Task 4(Structural DCM)\Automation Tool(Structural-CV Libraray)\cv_automation"

def patch_ai_classifier(dir_path):
    filepath = os.path.join(dir_path, "ai_classifier.py")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Add desired_role to JSON schema
    if '"desired_role":' not in content:
        content = content.replace(
            '"current_position": "string (extract ONLY the single most recent job title from the top of the candidate\'s Work Experience section. Do NOT combine titles. Output exactly what is written, e.g. \'Site Manager\')",\n',
            '"current_position": "string (extract ONLY the single most recent job title from the top of the candidate\'s Work Experience section. Do NOT combine titles. Output exactly what is written, e.g. \'Site Manager\')",\n  "desired_role": "string (extract the desired role or objective from the candidate\'s profile summary, or Unknown)",\n'
        )
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Patched {filepath}")

def patch_cv_library(dir_path):
    filepath = os.path.join(dir_path, "cv_library_searcher.py")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Instead of candidate.get("job_title", "Unknown"), use ai_result logic
    content = content.replace(
        '"job_title": candidate.get("job_title", "Unknown"),\n                        "desired_role": candidate.get("desired_role", "Unknown")',
        '"job_title": candidate.get("job_title", "Unknown") if candidate.get("job_title", "Unknown") != "Unknown" else ai_result.get("current_position", "Unknown"),\n                        "desired_role": candidate.get("desired_role", "Unknown") if candidate.get("desired_role", "Unknown") != "Unknown" else ai_result.get("desired_role", "Unknown")'
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Patched {filepath}")

def patch_totaljobs(dir_path):
    filepath = os.path.join(dir_path, "totaljobs_searcher.py")
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    content = content.replace(
        '"job_title": job_title_ext,\n                        "desired_role": desired_role_ext',
        '"job_title": job_title_ext if job_title_ext != "Unknown" else ai_result.get("current_position", "Unknown"),\n                        "desired_role": desired_role_ext if desired_role_ext != "Unknown" else ai_result.get("desired_role", "Unknown")'
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Patched {filepath}")

patch_ai_classifier(TASK_2_DIR)
patch_ai_classifier(TASK_4_DIR)
patch_cv_library(TASK_2_DIR)
patch_cv_library(TASK_4_DIR)
patch_totaljobs(TASK_2_DIR)
patch_totaljobs(TASK_4_DIR)
