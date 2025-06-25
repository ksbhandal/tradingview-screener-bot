import requests
from bs4 import BeautifulSoup
from flask import Flask
import threading
import time
from datetime import datetime
from pytz import timezone
import os

# Load ENV Vars
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SELF_URL = os.environ.get("SELF_URL")

URL = "https://www.tradingview.com/markets/stocks-usa/market-movers-pre-market-gainers/"
app = Flask(__name__)


def est_now():
    return datetime.now(timezone("US/Eastern"))


def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        print(f"Telegram error: {e}")


def parse_number(text):
    """Convert strings like '1.2K' or '3M' to a float."""
    if text is None:
        return 0
    text = text.replace(',', '').strip()
    if not text:
        return 0
    multipliers = {'K': 1_000, 'M': 1_000_000, 'B': 1_000_000_000, 'T': 1_000_000_000_000}
    last = text[-1]
    if last in multipliers:
        try:
            return float(text[:-1]) * multipliers[last]
        except ValueError:
            return 0
    try:
        return float(text)
    except ValueError:
        return 0


def scrape_and_notify():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/90.0"
        }
        res = requests.get(URL, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")

        rows = soup.select("div.tv-screener__content-pane div.tv-screener__row")
        if not rows:
            send_telegram_message("[ERROR] Screener content not found.")
            return

        results = []
        for row in rows[:25]:
            cols = row.select("div.tv-screener__cell")
            if len(cols) < 7:
                continue

            symbol = cols[0].get_text(strip=True)
            last = cols[1].get_text(strip=True)
            change_pct = cols[3].get_text(strip=True).replace('%', '')
            volume = cols[5].get_text(strip=True)
            market_cap = cols[6].get_text(strip=True)

            try:
                if (
                    float(change_pct) >= 10
                    and parse_number(volume) >= 100_000
                    and parse_number(market_cap) <= 500_000_000
                ):
                    results.append(
                        f"{symbol} | Price: {last} | Change: {change_pct}% | Vol: {volume} | Market Cap: {market_cap}"
                    )
            except Exception:
                continue

        if results:
            msg = f"🚀 Pre-Market Gainers @ {est_now().strftime('%I:%M %p')} EST\n\n"
            msg += "\n".join(results)
            send_telegram_message(msg)
        else:
            send_telegram_message("No qualifying stocks found in pre-market gainers.")

    except Exception as e:
        send_telegram_message(f"[ERROR] Failed to fetch pre-market gainers: {str(e)}")


@app.route("/")
def home():
    return "TradingView Screener Bot is live."


@app.route("/scan")
def scan():
    try:
        scrape_and_notify()
        return "Scan complete."
    except Exception as e:
        return f"Scan failed: {str(e)}"


if __name__ == "__main__":
    def ping_self():
        while True:
            now = est_now()
            if 4 <= now.hour < 9 or (now.hour == 9 and now.minute <= 30):
                try:
                    print(f"[Self-Ping] Triggering scan at {now.strftime('%I:%M %p')} EST")
                    requests.get(f"{SELF_URL}/scan")
                except Exception as e:
                    print(f"[Self-Ping Error] {e}")
            time.sleep(900)  # every 15 min

    threading.Thread(target=ping_self).start()
    app.run(host="0.0.0.0", port=10000)
