import json
import os

def convert_cookies():
    try:
        with open("raw_cv_cookies.json", "r") as f:
            raw_cookies = json.load(f)
            
        playwright_cookies = []
        for cookie in raw_cookies:
            pw_cookie = {
                "name": cookie.get("name", ""),
                "value": cookie.get("value", ""),
                "domain": cookie.get("domain", ""),
                "path": cookie.get("path", "/"),
                "expires": cookie.get("expirationDate", -1),
                "httpOnly": cookie.get("httpOnly", False),
                "secure": cookie.get("secure", False),
                "sameSite": "Lax" # Defaulting to Lax if unspecified, but Playwright accepts "Strict", "Lax", "None"
            }
            
            # Map sameSite correctly
            same_site = cookie.get("sameSite", "unspecified").lower()
            if same_site == "no_restriction" or same_site == "none":
                pw_cookie["sameSite"] = "None"
            elif same_site == "strict":
                pw_cookie["sameSite"] = "Strict"
            else:
                pw_cookie["sameSite"] = "Lax"
                
            playwright_cookies.append(pw_cookie)
            
        storage_state = {
            "cookies": playwright_cookies,
            "origins": []
        }
        
        with open("storage_state.json", "w") as f:
            json.dump(storage_state, f, indent=4)
            
        print("Successfully converted raw_cv_cookies.json to storage_state.json")
    except Exception as e:
        print(f"Error converting cookies: {e}")

if __name__ == "__main__":
    convert_cookies()
