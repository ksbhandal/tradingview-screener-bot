import os
import time
import threading
import requests
import asyncio
from flask import Flask
from datetime import datetime
from pytz import timezone
from playwright.async_api import async_playwright

# ENV Vars
TV_EMAIL = os.environ.get("TRADINGVIEW_EMAIL")
TV_PASSWORD = os.environ.get("TRADINGVIEW_PASSWORD")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SELF_URL = os.environ.get("SELF_URL")  # e.g. https://yourapp.onrender.com

SCREENER_URL = "https://www.tradingview.com/screener/pctXhfio/"
app = Flask(__name__)

def est_now():
    return datetime.now(timezone("US/Eastern"))

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        print(f"Telegram error: {e}")

async def login_and_scrape():
    try:
        # ✅ Ensure Chromium is always available at runtime
        os.system("playwright install chromium")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Login
            await page.goto("https://www.tradingview.com/#signin", timeout=60000)
            await page.wait_for_selector('[data-name="header-user-menu-sign-in"]', timeout=15000)
            await page.click('[data-name="header-user-menu-sign-in"]')
            await page.wait_for_selector("iframe[title='TradingView']", timeout=15000)

            frame = page.frame_locator("iframe[title='TradingView']")
            await frame.locator("input[name='username']").fill(TV_EMAIL)
            await frame.locator("input[name='password']").fill(TV_PASSWORD)
            await frame.locator("button[type='submit']").click()

            await page.wait_for_timeout(8000)
            await page.goto(SCREENER_URL)
            await page.wait_for_selector("table tr.tv-data-table__row", timeout=20000)

            rows = page.locator("table tr.tv-data-table__row")
            count = await rows.count()
            results = []

            for i in range(count):
                row = rows.nth(i)
                cols = row.locator("td")
                symbol = await cols.nth(0).inner_text()
                last = await cols.nth(1).inner_text()
                change = await cols.nth(2).inner_text()
                volume = await cols.nth(4).inner_text()
                results.append(f"{symbol.strip()} | Price: {last.strip()} | Change: {change.strip()} | Vol: {volume.strip()}")

            if results:
                msg = f"\U0001F680 TradingView Screener Results @ {est_now().strftime('%I:%M %p')} EST\n\n"
                msg += "\n".join(results)
                send_telegram_message(msg)
            else:
                send_telegram_message("No matching stocks found.")

            await browser.close()

    except Exception as e:
        send_telegram_message(f"[ERROR] Scan failed: {str(e)}")

@app.route("/")
def home():
    return "TradingView Screener Bot running..."

@app.route("/scan")
def scan():
    try:
        asyncio.run(login_and_scrape())
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
            time.sleep(600)

    threading.Thread(target=ping_self).start()
    app.run(host="0.0.0.0", port=10000)
