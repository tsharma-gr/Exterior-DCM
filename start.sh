#!/bin/bash
# Start X virtual framebuffer in the background
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Give Xvfb a moment to start
sleep 2

# Run the python app
python main.py
