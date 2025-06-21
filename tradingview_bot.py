import os
import time
import logging
import schedule
import pytz
import requests
from datetime import datetime
from flask import Flask, request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = os.environ.get('BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('CHAT_ID')
TRADINGVIEW_EMAIL = os.environ.get('TRADINGVIEW_EMAIL')
TRADINGVIEW_PASSWORD = os.environ.get('TRADINGVIEW_PASSWORD')
SECRET_KEY = os.environ.get('TRIGGER_SECRET_KEY', 'mysecret123')

# --- LOGGER ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- FLASK APP ---
app = Flask(__name__)

# --- TELEGRAM ALERT ---
def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, data=payload)
    except Exception as e:
        logger.error(f"Telegram error: {e}")

# --- SCAN FUNCTION ---
def run_screener():
    logger.info("Starting scan...")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get("https://www.tradingview.com")
        time.sleep(2)
        driver.find_element(By.LINK_TEXT, "Sign in").click()
        time.sleep(2)
        driver.find_element(By.XPATH, "//span[contains(text(),'Email')]").click()
        time.sleep(1)
        driver.find_element(By.NAME, "username").send_keys(TRADINGVIEW_EMAIL)
        driver.find_element(By.NAME, "password").send_keys(TRADINGVIEW_PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(8)
        driver.get("https://www.tradingview.com/screener/pctXhfio/")
        time.sleep(10)
        rows = driver.find_elements(By.XPATH, "//tbody/tr")

        results = []
        for row in rows:
            try:
                symbol = row.find_element(By.XPATH, ".//td[1]//a").text
                price = row.find_element(By.XPATH, ".//td[2]").text
                change = row.find_element(By.XPATH, ".//td[3]").text
                volume = row.find_element(By.XPATH, ".//td[4]").text
                market_cap = row.find_element(By.XPATH, ".//td[6]").text
                results.append(f"{symbol} | Price: {price} | Change: {change} | Vol: {volume} | MCap: {market_cap}")
            except Exception as e:
                logger.warning(f"Skipping row due to error: {e}")

        if results:
            logger.info(f"Found {len(results)} stocks")
            for r in results:
                send_telegram_message(r)
        else:
            send_telegram_message("[Scanner]: No matching stocks found at this time.")

    except Exception as e:
        logger.error(f"Scan failed: {e}")
    finally:
        driver.quit()

# --- TRIGGER SCAN ROUTE ---
@app.route("/trigger-scan", methods=["GET"])
def trigger_scan():
    key = request.args.get("key")
    if key != SECRET_KEY:
        return {"status": "unauthorized"}, 403
    try:
        run_screener()
        return {"status": "scan complete"}, 200
    except Exception as e:
        logger.error(f"Manual scan error: {e}")
        return {"status": "error", "message": str(e)}, 500

# --- MAIN LOOP ---
@app.route("/")
def home():
    return "TradingView Screener Bot Running"

if __name__ == '__main__':
    timezone = pytz.timezone("US/Eastern")
    schedule.every(10).minutes.do(run_screener)

    while True:
        now = datetime.now(timezone)
        if now.hour >= 9 and now.hour < 16:
            schedule.run_pending()
        time.sleep(30)
