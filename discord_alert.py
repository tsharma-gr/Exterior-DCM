import os
import time
import requests
import json
from openai import OpenAI
from logger_config import logger
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1531317261254656120/5sSQ6RhMjgBZpMklqAhbVLAYmbBwfB9vZSqFdTDsAY8Jt0cKOigLDox0mXVy7NDLbpui"

def test_api_balance():
    try:
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=base_url, timeout=30.0)
        else:
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=30.0)
            
        model = os.getenv("AI_MODEL", "gpt-4o-mini")
        
        # Make a tiny request to test if balance exists
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1
        )
        return True
    except Exception as e:
        err_str = str(e).lower()
        if any(x in err_str for x in ["insufficient_quota", "balance", "billing", "402", "credit", "rate limit reached", "too many requests"]):
            return False
        # If it's a completely different error (e.g. timeout), we assume balance is fine or we just let it return True so the main bot can retry
        return True

def send_discord_message(content):
    try:
        data = {"content": content}
        headers = {"Content-Type": "application/json"}
        requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers=headers, timeout=10)
    except Exception as e:
        logger.error(f"Failed to send Discord alert: {e}")

def pause_and_alert():
    logger.error("DeepSeek Balance Empty! Entering Deep Sleep Mode...")
    
    # Send emergency alert
    dcm_name = os.getenv("DCM_TYPE", "Unknown DCM")
    alert_msg = f"🚨 **URGENT**: `{dcm_name}` has run out of DeepSeek Balance (Error 402)! The bot has paused gracefully to protect CVs. Please top up the balance. The bot will automatically resume once funds are detected."
    send_discord_message(alert_msg)
    
    # Wait until balance is restored
    wait_time = 300 # 5 minutes between checks
    while True:
        logger.info("Bot is sleeping. Waiting for DeepSeek funds to be added...")
        time.sleep(wait_time)
        
        logger.info("Waking up to test DeepSeek API balance...")
        if test_api_balance():
            logger.info("DeepSeek balance is restored! Breaking Deep Sleep Mode. Resuming scraper...")
            success_msg = f"✅ **RESOLVED**: DeepSeek funds detected! `{dcm_name}` is waking up and resuming operations perfectly where it left off."
            send_discord_message(success_msg)
            break
        else:
            logger.error("DeepSeek balance still empty. Going back to sleep...")

import asyncio

async def pause_and_alert_email_verify(page):
    logger.error("TotalJobs Email Verification detected! Entering infinite pause loop...")
    
    dcm_name = os.getenv("DCM_TYPE", "Unknown DCM")
    alert_msg = f"🚨 **URGENT**: `{dcm_name}` requires TotalJobs Email Verification! The bot has PAUSED gracefully to protect your team member's inbox from spam. Please open the Remote Desktop Chrome window and enter the verification code. The bot will automatically resume once logged in."
    send_discord_message(alert_msg)
    
    wait_time = 5
    while True:
        logger.info("Bot is sleeping. Waiting for human to enter verification code...")
        await asyncio.sleep(wait_time)
        
        current_url = page.url.lower()
        # If the URL no longer contains verify, assume successful login
        if "verify" not in current_url and "verification" not in current_url and "safelistloginblocked" not in current_url:
            logger.info("URL changed! Human may have solved the verification. Resuming scraper...")
            success_msg = f"✅ **RESOLVED**: Verification bypassed on `{dcm_name}`! The bot is waking up and resuming operations perfectly where it left off."
            send_discord_message(success_msg)
            break
