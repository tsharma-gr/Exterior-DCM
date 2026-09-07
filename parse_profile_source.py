import os
import re

# Find files ending with .html
files = [f for f in os.listdir(".") if "profile_source.html" in f or "profile_source" in f]
# Filter out python scripts
files = [f for f in files if not f.endswith(".py")]

if not files:
    print("HTML files found in directory:")
    for f in os.listdir("."):
        if ".html" in f or "\\" in f:
            print(f"  {f}")
    exit(1)
    
fname = files[0]
print(f"Reading file: {fname}")

with open(fname, "r", encoding="utf-8") as f:
    content = f.read()
    
print(f"File length: {len(content)} characters")

# Find CV text or tabs
found_twinfix = "twinfix" in content.lower()
print(f"Twinfix in HTML: {found_twinfix}")

# Let's find all button texts and tab names
tags = re.findall(r'<(button|a|li)[^>]*>(.*?)</\1>', content, re.DOTALL)
print("\nFound Clickable Elements:")
count = 0
for tag_name, text in tags:
    clean_text = re.sub(r'<[^>]*>', '', text).strip()
    if clean_text and len(clean_text) < 60:
        print(f"  <{tag_name}>: {clean_text}")
        count += 1
        if count > 150:
            break
