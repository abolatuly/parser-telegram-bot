#!/bin/bash

# Navigate to the bot's directory
cd /root/bots/MontagneParfums

# Pull the latest code
git pull origin main

# Activate the virtual environment
source .venv/bin/activate

# Install/update dependencies
pip install -r requirements.txt

# Restart the bot using systemd
systemctl restart mybot.service