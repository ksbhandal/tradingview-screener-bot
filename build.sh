#!/bin/bash

pip install --upgrade pip
pip install -r requirements.txt

# Install Chromium browser for Python Playwright
python -m playwright install chromium
