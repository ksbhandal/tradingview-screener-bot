import os
import time
import threading
import asyncio
import requests
from flask import Flask
from datetime import datetime
from pytz import timezone
from playwright.async_api import async_playwright

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SELF_URL = os.getenv("SELF_URL")

TRADINGVIEW_URL = "https://www.tradingview.com/markets/stocks-usa/market-movers-pre-market-gainers/"
app = Flask(__name__)

def est_now():
    return datetime.now(timezone("US/Eastern"))

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        print(f"Telegram error: {e}")

async def scrape_tradingview():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(TRADINGVIEW_URL, timeout=60000)
            await page.wait_for_selector("table tr", timeout=20000)

            rows = await page.locator("table tr").all()
            results = []

            for row in rows[1:26]:  # Skip header, take top 25
                cols = await row.locator("td").all()
                if len(cols) < 5:
                    continue
                symbol = await cols[0].inner_text()
                name = await cols[1].inner_text()
                price = await cols[2].inner_text()
                change = await cols[3].inner_text()
                volume = await cols[4].inner_text()

                try:
                    percent = float(change.strip('%+').replace(',', ''))
                    if percent >= 10:
                        results.append(f"{symbol.strip()} | {price.strip()} | {change.strip()} | Vol: {volume.strip()}")
                except:
                    continue

            if results:
                msg = f"\U0001F680 Premarket Gainers @ {est_now().strftime('%I:%M %p')} EST\n\n"
                msg += "\n".join(results)
                send_telegram_message(msg)
            else:
                send_telegram_message("No qualifying premarket stocks found.")

            await browser.close()

    except Exception as e:
        send_telegram_message(f"[ERROR] Scrape failed: {str(e)}")

@app.route("/")
def home():
    return "TradingView PreMarket Bot is running..."

@app.route("/scan")
def scan():
    try:
        asyncio.run(scrape_tradingview())
        return "Scan complete."
    except Exception as e:
        return f"Scan failed: {str(e)}"

if __name__ == "__main__":
    def ping_self():
        while True:
            now = est_now()
            if 4 <= now.hour < 9 or (now.hour == 9 and now.minute <= 30):
                try:
                    print(f"Pinging self at {now.strftime('%I:%M %p')} EST")
                    requests.get(f"{SELF_URL}/scan")
                except Exception as e:
                    print(f"Self-ping failed: {e}")
            time.sleep(600)  # Every 10 mins

    threading.Thread(target=ping_self).start()
    app.run(host="0.0.0.0", port=10000)
