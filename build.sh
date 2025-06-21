#!/bin/bash

# Install Playwright dependencies
pip install -r requirements.txt

# Install browser binaries (Chromium) for Playwright
python -m playwright install --with-deps
