import os
import time
import threading
import requests
import asyncio
from flask import Flask
from datetime import datetime
from pytz import timezone
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

TV_EMAIL = os.getenv("TRADINGVIEW_EMAIL")
TV_PASSWORD = os.getenv("TRADINGVIEW_PASSWORD")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SELF_URL = os.getenv("SELF_URL")

SCREENER_URL = "https://www.tradingview.com/screener/pctXhfio/"
app = Flask(__name__)


def est_now():
    return datetime.now(timezone("US/Eastern"))


def send_telegram_message(message: str) -> None:
    """Send a Telegram message using the configured bot."""
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram credentials missing")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as exc:
        print(f"Telegram error: {exc}")


async def login_and_scrape() -> None:
    """Login to TradingView and scrape the configured screener."""
    if not TV_EMAIL or not TV_PASSWORD:
        send_telegram_message("[ERROR] TradingView credentials are missing.")
        return

    os.system("playwright install chromium")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-dev-shm-usage"])
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://www.tradingview.com/accounts/signin/", timeout=90000)

        try:
            # locate the iframe that hosts the TradingView login form
            await page.wait_for_selector("iframe", timeout=30000)
            login_frame = None
            for _ in range(20):
                for frame in page.frames:
                    try:
                        await frame.wait_for_selector("input[name='username']", timeout=1000)
                        login_frame = frame
                        break
                    except PlaywrightTimeout:
                        continue
                if login_frame:
                    break
                await asyncio.sleep(1)

            if not login_frame:
                raise PlaywrightTimeout("Login iframe not found")

            await login_frame.fill("input[name='username']", TV_EMAIL)
            await login_frame.click("button[type='submit']")
            await login_frame.wait_for_selector("input[type='password']", timeout=15000)
            await login_frame.fill("input[type='password']", TV_PASSWORD)
            await login_frame.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")
        except PlaywrightTimeout:
            send_telegram_message("[ERROR] Login form did not load correctly.")
            await browser.close()
            return

        await page.goto(SCREENER_URL, timeout=30000)
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


@app.route("/")
def home():
    return "TradingView Screener Bot running..."


@app.route("/scan")
def scan():
    try:
        asyncio.run(login_and_scrape())
        return "Scan complete."
    except Exception as exc:
        return f"Scan failed: {exc}"


if __name__ == "__main__":
    def ping_self():
        while True:
            now = est_now()
            if now.hour >= 9 and (now.hour < 16 or (now.hour == 16 and now.minute == 0)):
                if now.hour > 9 or now.minute >= 30:
                    try:
                        print(f"Pinging self at {now.strftime('%I:%M %p')} EST")
                        requests.get(f"{SELF_URL}/scan")
                    except Exception as exc:
                        print(f"Self-ping failed: {exc}")
            time.sleep(600)

    threading.Thread(target=ping_self).start()
    app.run(host="0.0.0.0", port=10000)
