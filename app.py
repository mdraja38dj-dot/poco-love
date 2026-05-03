import os
import time
import threading
import requests
import yfinance as yf
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask("poco_love")
CORS(app)

API_KEY = os.environ.get("GEMINI_API_KEY", "")

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-1.5-flash:generateContent?key={API_KEY}"
)

latest_signal = {}
analysis_lock = False


# ================= HOME =================
@app.route("/")
def home():
    return jsonify({
        "server": "POCO LOVE ❤️",
        "status": "LIVE",
        "system": "BUTTON + LAST SECOND AI SIGNAL ENGINE"
    })


# ================= MARKET DATA =================
def get_data(symbol):
    try:
        ticker = "EURUSD=X"

        if "BTC" in symbol:
            ticker = "BTC-USD"
        elif "XAU" in symbol:
            ticker = "GC=F"

        df = yf.download(
            ticker,
            period="1d",
            interval="1m",
            progress=False
        )

        if df is None or df.empty:
            return None

        return df.tail(100)

    except:
        return None


# ================= INDICATORS =================
def indicators(df):
    ema20 = df["Close"].ewm(span=20).mean().iloc[-1]
    ema50 = df["Close"].ewm(span=50).mean().iloc[-1]

    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()

    rs = gain / (loss + 1e-9)
    rsi = 100 - (100 / (1 + rs)).iloc[-1]

    last = df.iloc[-1]
    candle = "GREEN" if last["Close"] > last["Open"] else "RED"

    return ema20, ema50, rsi, candle


# ================= SMC LOGIC =================
def bos(df):
    if df["Close"].iloc[-1] > df["High"].iloc[-3]:
        return "BOS_UP"
    elif df["Close"].iloc[-1] < df["Low"].iloc[-3]:
        return "BOS_DOWN"
    return "NONE"


def choch(df):
    prev = df.iloc[-2]
    last = df.iloc[-1]

    if prev["Close"] < prev["Open"] and last["Close"] > last["Open"]:
        return "BULLISH_CHoCH"
    if prev["Close"] > prev["Open"] and last["Close"] < last["Open"]:
        return "BEARISH_CHoCH"
    return "NONE"


def liquidity(df):
    last = df.iloc[-1]
    high_zone = df["High"].iloc[-5]
    low_zone = df["Low"].iloc[-5]

    if last["High"] > high_zone and last["Close"] < last["Open"]:
        return "SELL_SIDE_GRAB"
    if last["Low"] < low_zone and last["Close"] > last["Open"]:
        return "BUY_SIDE_GRAB"
    return "NONE"


def order_block(df):
    for i in range(-5, -20, -1):
        c = df.iloc[i]
        n = df.iloc[i + 1]

        if c["Close"] < c["Open"] and n["Close"] > n["Open"]:
            return "BULLISH_OB"
        if c["Close"] > c["Open"] and n["Close"] < n["Open"]:
            return "BEARISH_OB"

    return "NONE"


# ================= SCORE ENGINE =================
def score_engine(df):
    score = 0

    ema20, ema50, rsi, candle = indicators(df)

    trend = "UP" if ema20 > ema50 else "DOWN"

    # trend
    score += 2 if trend == "UP" else -2

    # rsi
    if rsi < 30:
        score += 2
    elif rsi > 70:
        score -= 2

    # SMC signals
    b = bos(df)
    c = choch(df)
    l = liquidity(df)
    o = order_block(df)

    if b == "BOS_UP":
        score += 3
    elif b == "BOS_DOWN":
        score -= 3

    if c == "BULLISH_CHoCH":
        score += 2
    elif c == "BEARISH_CHoCH":
        score -= 2

    if l == "BUY_SIDE_GRAB":
        score += 2
    elif l == "SELL_SIDE_GRAB":
        score -= 2

    if o == "BULLISH_OB":
        score += 2
    elif o == "BEARISH_OB":
        score -= 2

    context = {
        "trend": trend,
        "ema20": float(ema20),
        "ema50": float(ema50),
        "rsi": float(rsi),
        "candle": candle,
        "bos": b,
        "choch": c,
        "liquidity": l,
        "order_block": o
    }

    return score, context


# ================= SIGNAL =================
def get_signal(score):
    if score >= 6:
        return "CALL"
    elif score <= -6:
        return "PUT"
    return "WAIT"


# ================= GEMINI =================
def gemini(prompt):
    try:
        if not API_KEY:
            return "NO API KEY"

        r = requests.post(GEMINI_URL, json={
            "contents": [{"parts": [{"text": prompt}]}]
        }, timeout=10)

        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    except:
        return "AI ERROR"


# ================= LAST SECOND ENGINE =================
def last_second_engine(market):
    global latest_signal, analysis_lock

    analysis_lock = True

    try:
        now = time.time()
        wait = 60 - (now % 60)

        # sync near candle close
        if wait > 2:
            time.sleep(wait - 2)

        df = get_data(market)

        if df is None:
            latest_signal = {"signal": "WAIT", "reason": "NO DATA"}
            analysis_lock = False
            return

        score, ctx = score_engine(df)
        sig = get_signal(score)

        prompt = f"""
Market: {market}
Signal: {sig}
Trend: {ctx['trend']}
Candle: {ctx['candle']}
RSI: {ctx['rsi']}

Explain briefly like a trader.
"""

        ai = gemini(prompt)

        latest_signal = {
            "market": market,
            "signal": sig,
            "score": score,
            "context": ctx,
            "ai": ai,
            "mode": "LAST_SECOND_SIGNAL"
        }

    except:
        latest_signal = {"signal": "WAIT", "error": True}

    analysis_lock = False


# ================= API: BUTTON CLICK =================
@app.route("/analyze")
def analyze():
    market = request.args.get("market", "EURUSD")

    if not analysis_lock:
        threading.Thread(target=last_second_engine, args=(market,), daemon=True).start()

    return jsonify({
        "status": "ANALYSIS STARTED",
        "market": market
    })


# ================= API: GET SIGNAL =================
@app.route("/signal")
def signal():
    return jsonify(latest_signal)


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
