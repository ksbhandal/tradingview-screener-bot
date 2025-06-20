import os
import time
import pytz
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from flask import Flask

# Load environment variables
TV_USERNAME = os.environ.get("TV_USERNAME")
TV_PASSWORD = os.environ.get("TV_PASSWORD")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

app = Flask(__name__)

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Telegram Error:", e)


def is_market_open():
    est = pytz.timezone("US/Eastern")
    now = datetime.now(est)
    return now.weekday() < 5 and now.hour >= 9 and now.hour < 16


def scrape_tradingview():
    print("Starting TradingView scraping")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get("https://www.tradingview.com")
        time.sleep(5)

        login_button = driver.find_element(By.XPATH, '//button[contains(text(), "Log in")]')
        login_button.click()
        time.sleep(3)

        driver.find_element(By.XPATH, '//span[contains(text(), "Email")]').click()
        time.sleep(2)

        driver.find_element(By.NAME, "username").send_keys(TV_USERNAME)
        driver.find_element(By.NAME, "password").send_keys(TV_PASSWORD)
        driver.find_element(By.XPATH, '//button[@type="submit"]').click()
        time.sleep(8)

        # Navigate to custom screener URL
        driver.get("https://www.tradingview.com/screener/" + "your-screener-link-slug")
        time.sleep(10)

        rows = driver.find_elements(By.CSS_SELECTOR, 'table tr[data-row-key]')
        results = []
        for row in rows:
            try:
                symbol = row.find_element(By.CSS_SELECTOR, 'td[data-field-key="ticker"]').text
                price = row.find_element(By.CSS_SELECTOR, 'td[data-field-key="close"]').text
                change = row.find_element(By.CSS_SELECTOR, 'td[data-field-key="change"]').text
                results.append(f"{symbol} | {price} | Change: {change}")
            except Exception:
                continue

        if results:
            send_telegram_message("\n".join(results[:15]))  # Send top 15 only
        else:
            send_telegram_message("No qualifying stocks found.")

    except Exception as e:
        print("Scraping failed:", e)
        send_telegram_message("Error during scraping TradingView")
    finally:
        driver.quit()


@app.route("/")
def home():
    return "Service running"

@app.route("/scan")
def scan():
    if is_market_open():
        scrape_tradingview()
        return "Scan complete"
    else:
        return "Market closed"

@app.route("/ping")
def ping():
    return "pong"

if __name__ == '__main__':
    app.run(debug=True, port=10000, host='0.0.0.0')
