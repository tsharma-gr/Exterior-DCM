import re

with open('/root/structural_cv_automation/totaljobs_searcher.py') as f:
    text = f.read()

# Let's print around Case B and go_back references
print("--- Case B block in structural ---")
match = re.search(r'# Check if the main page navigated to a different URL \(Case B\).*?# Go back to the search results.*?\n\s*\n', text, re.DOTALL)
if match:
    print(match.group(0))
else:
    print("Case B block not found by regex. Printing lines 820-950:")
    lines = text.split("\n")
    for idx in range(820, min(950, len(lines))):
        print(f"{idx+1}: {lines[idx]}")

print("\n--- All occurrences of go_back or goto in structural ---")
for idx, line in enumerate(text.split("\n")):
    if "go_back" in line or "goto" in line:
        print(f"Line {idx+1}: {line.strip()}")
