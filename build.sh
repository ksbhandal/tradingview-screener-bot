#!/bin/bash
set -e

pip install --upgrade pip
pip install -r requirements.txt

# install the Playwright browser binaries without requiring sudo
python -m playwright install chromium
