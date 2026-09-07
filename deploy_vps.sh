#!/bin/bash
set -e

echo "========================================"
echo " DigitalOcean VPS Deployment Setup      "
echo "========================================"

# 1. System Updates and Dependencies
echo "[1/5] Updating system and installing dependencies..."
sudo apt-get update -y
sudo apt-get install -y python3.12 python3.12-venv python3-pip curl git xvfb tzdata

# 2. Set Timezone to UK Time
echo "[2/5] Setting Server Timezone to Europe/London..."
sudo timedatectl set-timezone Europe/London

# 3. Virtual Environment Setup
echo "[3/5] Setting up Virtual Environment..."
cd "$(dirname "$0")"
APP_DIR=$(pwd)

if [ ! -d ".venv" ]; then
    python3.12 -m venv .venv
fi
source .venv/bin/activate

# 4. Python Dependencies and Playwright
echo "[4/5] Installing Python packages and Playwright browsers..."
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium --with-deps

# 5. Create Logs Directory
mkdir -p logs

# 6. Configure Crontab
echo "[5/5] Configuring Cron Job for 2:00 AM UK Time..."

# We use xvfb-run -a to simulate a real monitor so HEADLESS=false works!
CRON_CMD="0 2 * * * cd $APP_DIR && xvfb-run -a .venv/bin/python main.py >> logs/automation.log 2>&1"

# Check if cron job already exists
(crontab -l 2>/dev/null | grep -v "$APP_DIR/main.py") | crontab -
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo "========================================"
echo " Deployment Complete! "
echo " - Your environment is set up at: $APP_DIR"
echo " - Server timezone is set to Europe/London"
echo " - Cron is scheduled to run daily at 2:00 AM."
echo " - Logs will be saved to: $APP_DIR/logs/automation.log"
echo "========================================"
