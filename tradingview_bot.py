import requests
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
app = Flask(__name__)

def est_now():
    return datetime.now(timezone("US/Eastern"))

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        print(f"Telegram error: {e}")

def scrape_and_notify():
    try:
        payload = {
            "filter": [
                {"left": "type", "operation": "equal", "right": "stock"},
                {"left": "change", "operation": "greater", "right": 10},
                {"left": "volume", "operation": "greater", "right": 100000},
                {"left": "market_cap_basic", "operation": "less", "right": 500000000}
            ],
            "options": {"lang": "en"},
            "symbols": {"query": {"types": []}, "tickers": []},
            "columns": ["name", "close", "change", "volume", "market_cap_basic"],
            "sort": {"sortBy": "change", "sortOrder": "desc"},
            "range": [0, 50],
        }

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "Referer": "https://www.tradingview.com/",
            "Origin": "https://www.tradingview.com",
        }

        res = requests.post(
            "https://scanner.tradingview.com/america/scan",
            json=payload,
            headers=headers,
            timeout=10,
        )

        if res.status_code != 200:
            send_telegram_message(
                f"[ERROR] Screener request failed: HTTP {res.status_code}"
            )
            return

        try:
            data = res.json().get("data", [])
        except ValueError:
            send_telegram_message("[ERROR] Invalid JSON received from screener")
            return

        if not data:
            send_telegram_message("No qualifying stocks found in pre-market gainers.")
            return

        results = []
        for row in data:
            values = row.get("d", [])
            if len(values) < 5:
                continue

            symbol = row.get("s", "")
            last = values[1]
            change_pct = values[2]
            volume = values[3]
            market_cap = values[4]

            exchange = symbol.split(":")[0]
            price = float(last) if last else 0

            if (
                change_pct >= 10
                and volume >= 100000
                and market_cap is not None and market_cap >= 10_000_000
                and price >= 0.5
                and exchange in ["NASDAQ", "NYSE"]
            ):
                results.append(
                    f"📈 {symbol}\n"
                    f"💵 Price: ${price:.4f}   | 📊 Change: +{change_pct:.2f}%\n"
                    f"📦 Volume: {int(volume):,}  | 🏦 MCap: ${int(market_cap):,}\n"
                )

        if results:
            msg = f"🌅 Pre-Market Gainers @ {est_now().strftime('%I:%M %p')} EST\n"
            msg += f"🧮 Total: {len(results)} stocks\n\n"
            msg += "\n".join(results[:25])
            send_telegram_message(msg)
        else:
            send_telegram_message("⚠️ No clean gainers found above 10% with safe filters.")

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
            time.sleep(900)  # every 15 minutes

    threading.Thread(target=ping_self).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
