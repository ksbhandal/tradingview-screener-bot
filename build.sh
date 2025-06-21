#!/bin/bash

# Install Google Chrome for headless scraping
apt-get update
apt-get install -y wget gnupg unzip
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt install -y ./google-chrome-stable_current_amd64.deb

# Optional: Install chromedriver (if used in your script)
# LATEST=$(wget -q -O - https://chromedriver.storage.googleapis.com/LATEST_RELEASE)
# wget https://chromedriver.storage.googleapis.com/${LATEST}/chromedriver_linux64.zip
# unzip chromedriver_linux64.zip
# mv chromedriver /usr/bin/chromedriver
# chmod +x /usr/bin/chromedriver
