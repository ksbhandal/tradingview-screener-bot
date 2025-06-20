import os
import requests
from flask import Flask
import threading
import time
from datetime import datetime
from pytz import timezone
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Load from environment
TV_EMAIL = os.environ.get("tv_email")
TV_PASSWORD = os.environ.get("tv_password")
BOT_TOKEN = os.environ.get("bot_token")
CHAT_ID = os.environ.get("chat_id")
SELF_URL = os.environ.get("SELF_URL")  # e.g. https://yourapp.onrender.com

SCREENER_URL = "https://www.tradingview.com/screener/pctXhfio/"
app = Flask(__name__)

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        print(f"Telegram error: {e}")

def est_now():
    return datetime.now(timezone("US/Eastern"))

def login_and_scrape():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get("https://www.tradingview.com/#signin")
        time.sleep(5)

        login_btn = driver.find_element(By.CSS_SELECTOR, '[data-name="header-user-menu-sign-in"]')
        login_btn.click()
        time.sleep(3)

        driver.switch_to.frame(driver.find_element(By.CSS_SELECTOR, "iframe[title='TradingView']"))
        driver.find_element(By.NAME, "username").send_keys(TV_EMAIL)
        driver.find_element(By.NAME, "password").send_keys(TV_PASSWORD)
        driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        time.sleep(8)
        driver.switch_to.default_content()

        driver.get(SCREENER_URL)
        time.sleep(10)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        rows = soup.select("table tr.tv-data-table__row")

        results = []
        for row in rows:
            cols = row.find_all("td")
            if not cols:
                continue
            symbol = cols[0].text.strip()
            last = cols[1].text.strip()
            change = cols[2].text.strip()
            volume = cols[4].text.strip()
            results.append(f"{symbol} | Price: {last} | Change: {change} | Vol: {volume}")

        if results:
            msg = f"\U0001F680 TradingView Screener Results @ {est_now().strftime('%I:%M %p')} EST\n\n"
            msg += "\n".join(results)
            send_telegram_message(msg)
        else:
            send_telegram_message("No matching stocks found.")

    except Exception as e:
        send_telegram_message(f"[ERROR] Scan failed: {str(e)}")

    finally:
        driver.quit()

@app.route("/")
def home():
    return "TradingView Screener Bot running..."

@app.route("/scan")
def scan():
    try:
        login_and_scrape()
        return "Scan complete."
    except Exception as e:
        return f"Scan failed: {str(e)}"

if __name__ == "__main__":
    def ping_self():
        while True:
            now = est_now()
            if now.hour >= 9 and (now.hour < 16 or (now.hour == 16 and now.minute == 0)):
                if now.hour > 9 or now.minute >= 30:
                    try:
                        print(f"Pinging self at {now.strftime('%I:%M %p')} EST")
                        requests.get(f"{SELF_URL}/scan")
                    except Exception as e:
                        print(f"Self-ping failed: {e}")
            time.sleep(600)  # every 10 minutes

    threading.Thread(target=ping_self).start()
    app.run(host="0.0.0.0", port=10000)
