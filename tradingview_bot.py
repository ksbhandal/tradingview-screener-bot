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

URL = "https://scanner.tradingview.com/america/scan"
app = Flask(__name__)


def est_now():
    return datetime.now(timezone("US/Eastern"))


def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        res = requests.post(
            url, data={"chat_id": CHAT_ID, "text": message}, timeout=10
        )
        res.raise_for_status()
    except requests.RequestException as e:
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
        payload = {
            "filter": [
                {"left": "is_premarket", "operation": "equal", "right": True},
                {"left": "change", "operation": "greater_or_equal", "right": 10},
                {"left": "volume", "operation": "greater_or_equal", "right": 100000},
                {
                    "left": "market_cap_basic",
                    "operation": "less_or_equal",
                    "right": 500000000,
                },
            ],
            "symbols": {"tickers": [], "query": {"types": []}},
            "columns": [
                "name",
                "close",
                "change",
                "volume",
                "market_cap_basic",
            ],
            "sort": {"sortBy": "change", "sortOrder": "desc"},
            "range": [0, 25],
        }

        try:
            res = requests.post(URL, json=payload, headers=headers, timeout=10)
            res.raise_for_status()
        except requests.RequestException as e:
            send_telegram_message(f"[ERROR] HTTP request failed: {e}")
            return

        data = res.json().get("data", [])

        results = []
        for item in data:
            try:
                symbol = item.get("s", "-")
                name, last, change_pct, volume, market_cap = item.get("d", [None] * 5)
                if (
                    float(change_pct) >= 10
                    and parse_number(str(volume)) >= 100_000
                    and parse_number(str(market_cap)) <= 500_000_000
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
