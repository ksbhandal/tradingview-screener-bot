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
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "MarkdownV2"
        })
    except Exception as e:
        print(f"Telegram error: {e}")

# Helper to escape special MarkdownV2 characters
def escape_md(text):
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    return ''.join(f'\\{c}' if c in escape_chars else c for c in str(text))

def scrape_and_notify():
    try:
        payload = {
            "filter": [
                {"left": "type", "operation": "equal", "right": "stock"},
                {"left": "change", "operation": "greater", "right": 10},
                {"left": "volume", "operation": "greater", "right": 100000},
                {"left": "market_cap_basic", "operation": "less", "right": 500000000},
                {"left": "market_cap_basic", "operation": "greater", "right": 10000000},
                {"left": "close", "operation": "greater", "right": 0.5}
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
            send_telegram_message(f"[ERROR] Screener request failed: HTTP {res.status_code}")
            return

        data = res.json().get("data", [])
        if not data:
            send_telegram_message("📉 No pre-market gainers found right now.")
            return

        results = []
        for row in data:
            values = row.get("d", [])
            if len(values) < 5:
                continue

            symbol = escape_md(row.get("s", ""))
            price = escape_md(f"{values[1]:.4f}")
            change_pct = escape_md(f"{values[2]:.2f}")
            volume = escape_md(f"{int(values[3]):,}")
            market_cap = escape_md(f"{int(values[4]):,}")

            exchange = symbol.split("\\:")[0]  # Escaped colon
            if exchange not in ["NASDAQ", "NYSE"]:
                continue

            results.append(
                f"📈 *{symbol}*\n"
                f"💵 Price: ${price}   | 📊 Change: +{change_pct}%\n"
                f"📦 Volume: {volume}  | 🏦 MCap: ${market_cap}\n"
            )

        if results:
            msg = f"🌅 *Pre\\-Market Gainers* @ {escape_md(est_now().strftime('%I:%M %p'))} EST\n"
            msg += f"🧮 Total: {len(results)} stocks\n\n"
            msg += "\n".join(results)
            send_telegram_message(msg)
        else:
            send_telegram_message("📉 No qualifying pre-market gainers found.")

    except Exception as e:
        send_telegram_message(f"[ERROR] Failed to fetch pre-market gainers: {escape_md(e)}")

@app.route("/")
def home():
    return "Pre-Market Screener Bot is live."

@app.route("/scan")
def scan():
    try:
        scrape_and_notify()
        return "Pre-market scan complete."
    except Exception as e:
        return f"Scan failed: {str(e)}"

if __name__ == "__main__":
    def ping_self():
        while True:
            now = est_now()
            if 4 <= now.hour < 9 or (now.hour == 9 and now.minute <= 30):
                try:
                    print(f"[Self-Ping] Triggering pre-market scan @ {now.strftime('%I:%M %p')} EST")
                    requests.get(f"{SELF_URL}/scan")
                except Exception as e:
                    print(f"[Self-Ping Error] {e}")
            time.sleep(900)  # every 15 minutes

    threading.Thread(target=ping_self).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
