from flask import Flask, jsonify, request
from datetime import datetime
import yfinance as yf
import traceback

app = Flask(__name__)

# ==============================================================================
# 🚀 LEVEL-8 "PURE INSTITUTIONAL" ENGINE (LIGHTWEIGHT & STABLE)
# ==============================================================================

def get_session_profile_dubai():
    """Returns session name and volatility multiplier (Dubai UTC+4)."""
    try:
        if hasattr(datetime, 'utcnow'):
             utc_hour = datetime.utcnow().hour
        else:
             utc_hour = datetime.now().hour # Fallback
             
        dubai_hour = (utc_hour + 4) % 24
        
        if 2 <= dubai_hour < 12: return "ASIAN (RANGE)", 0.7 
        if 12 <= dubai_hour < 17: return "LONDON (BREAKOUT)", 1.2
        if 17 <= dubai_hour < 21: return "OVERLAP (STRONGEST)", 1.6 
        if 21 <= dubai_hour < 23: return "NY (VOLATILE)", 1.4
        return "LATE NY (FADE)", 0.9
    except:
        return "MARKET", 1.0

# --- PURE PYTHON INDICATORS (NO PANDAS) ---

def calculate_ema(prices, period):
    if len(prices) < period: return 0
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period # Simple AVG for first EMA
    for price in prices[period:]:
        ema = (price * k) + (ema * (1 - k))
    return ema

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1: return 50
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        delta = prices[i] - prices[i-1]
        if delta > 0:
            gains.append(delta)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(delta))
            
    # First Average
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Wilder's Smoothing
    for i in range(period, len(prices)-1):
        delta = prices[i+1] - prices[i]
        gain = delta if delta > 0 else 0
        loss = abs(delta) if delta < 0 else 0
        
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        
    if avg_loss == 0: return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_atr(highs, lows, closes, period=14):
    if len(closes) < period + 1: return 1.0
    tr_list = []
    for i in range(1, len(closes)):
        h = highs[i]; l = lows[i]; c_prev = closes[i-1]
        tr = max(h-l, abs(h-c_prev), abs(l-c_prev))
        tr_list.append(tr)
        
    # Smoothed ATR
    atr = sum(tr_list[:period]) / period
    for i in range(period, len(tr_list)):
        atr = ((atr * (period - 1)) + tr_list[i]) / period
    return atr

def fetch_live_data(interval):
    """
    Fetches REAL market data.
    """
    try:
        yf_interval = interval
        period = "60d" # Max for 5m/15m
        
        if interval == "1h": period = "1y"
        elif interval == "1d": period = "2y"

        tickers = ["GC=F", "DX-Y.NYB", "^TNX"]
        
        # Download (returns dict of DataFrames, but we cast to list)
        data = yf.download(tickers, period=period, interval=yf_interval, progress=False, group_by='ticker')
        
        response = {}
        
        # Process Gold (Main Asset)
        if "GC=F" in data:
            df = data["GC=F"].dropna()
            
            # Convert to Lists for processing
            response["OPENS"] = df['Open'].tolist()
            response["HIGHS"] = df['High'].tolist()
            response["LOWS"] = df['Low'].tolist()
            response["CLOSES"] = df['Close'].tolist()
            response["VOLUMES"] = df['Volume'].tolist()

        if "DX-Y.NYB" in data:
            response["DXY_CLOSES"] = data["DX-Y.NYB"]['Close'].dropna().tolist()
        else:
             response["DXY_CLOSES"] = []

        return response
    except Exception as e:
        print(f"Data Fetch Error: {e}")
        return None

def calculate_logic(data_pack, session_name, session_vol):
    """
    LEVEL-8 ENGINE (Lightweight)
    """
    if not data_pack or "CLOSES" not in data_pack or len(data_pack["CLOSES"]) < 200:
         return {"signal": "WAIT", "formatted_report": "System Offline", "lock": True}
    
    closes = data_pack["CLOSES"]
    opens = data_pack["OPENS"]
    highs = data_pack["HIGHS"]
    lows = data_pack["LOWS"]
    volumes = data_pack["VOLUMES"]
    dxy_series = data_pack["DXY_CLOSES"]
    
    # Current Candle
    price = closes[-1]
    
    # --- A. INSTITUTIONAL TREND (EMA) ---
    ema200 = calculate_ema(closes, 200)
    ema50 = calculate_ema(closes, 50)
    ema21 = calculate_ema(closes, 21)
    
    trend = "NEUTRAL"
    if price > ema200 and ema21 > ema50: trend = "BULLISH"
    elif price < ema200 and ema21 < ema50: trend = "BEARISH"
    
    # --- B. VSA & MOMENTUM ---
    # Calc VSA
    vol_avg = sum(volumes[-21:-1]) / 20 if len(volumes) > 20 else 1
    vsa_confirm = volumes[-1] > (vol_avg * 1.5)
    
    # Calc Expansion
    body = abs(closes[-1] - opens[-1])
    # avg range 50
    ranges = [(h-l) for h, l in zip(highs[-51:-1], lows[-51:-1])]
    avg_range = sum(ranges) / len(ranges) if ranges else 1
    is_expansion = body > (avg_range * 1.8)
    
    # Calc RSI
    rsi = calculate_rsi(closes, 14)
    
    # --- C. CORRELATION (DXY SHOCK) ---
    lock_reason = None
    is_locked = False
    if len(dxy_series) > 10:
        d_delta = abs(dxy_series[-1] - dxy_series[-2])
        if d_delta > 0.15: 
            is_locked = True
            lock_reason = "VOLATILITY SHOCK"
            
    # --- D. SCORING ENGINE ---
    score = 50
    if trend == "BULLISH": score += 20
    elif trend == "BEARISH": score -= 20
    
    if vsa_confirm:
        if closes[-1] > opens[-1]: score += 10
        else: score -= 10
        
    if is_expansion:
        if closes[-1] > opens[-1]: score += 10
        else: score -= 10
        
    if rsi > 58: score += 10
    elif rsi < 42: score -= 10
    
    score = 50 + ((score - 50) * session_vol)
    
    # --- E. FINAL SIGNAL & EXNESS LEVELS ---
    buy_prob = int(score)
    sell_prob = int(100 - score)
    signal = "WAIT"
    sl = tp = 0.0
    atr = calculate_atr(highs, lows, closes, 14)
    
    if is_locked:
        signal = f"WAIT ({lock_reason})"
    else:
        if buy_prob >= 70 and (vsa_confirm or is_expansion):
            signal = "STRONG BUY"
            sl = price - (2.0 * atr)
            tp = price + (3.5 * atr) 
        elif sell_prob >= 70 and (vsa_confirm or is_expansion):
            signal = "STRONG SELL"
            sl = price + (2.0 * atr)
            tp = price - (3.5 * atr)
        elif buy_prob >= 60 and trend == "BULLISH":
            signal = "BUY"
            sl = price - (1.5 * atr)
            tp = price + (2.5 * atr)
        elif sell_prob >= 60 and trend == "BEARISH":
            signal = "SELL"
            sl = price + (1.5 * atr)
            tp = price - (2.5 * atr)
            
    # --- F. PREDICTIVE FORECAST ---
    forecast = "NEUTRAL (WAIT)"
    if signal.startswith("STRONG BUY"):
        forecast = "HIGH PROBABILITY CONTINUATION (BUY)"
    elif signal.startswith("STRONG SELL"):
        forecast = "HIGH PROBABILITY CONTINUATION (SELL)"
    elif "BUY" in signal and rsi < 65:
        forecast = "PROBABLE UPSIDE (BUY)"
    elif "SELL" in signal and rsi > 35:
        forecast = "PROBABLE DOWNSIDE (SELL)"
    elif is_locked:
        forecast = "STAY OUT (DANGEROUS)"
    else:
        forecast = "CONSOLIDATION (WAIT)"

    return {
        "signal": signal,
        "forecast": forecast,
        "probs": {"buy": buy_prob, "sell": sell_prob},
        "trend": trend,
        "rsi": round(rsi, 1),
        "vsa": "BIG MONEY" if vsa_confirm else "NORMAL",
        "expansion": "HIGH" if is_expansion else "LOW",
        "lock": is_locked,
        "levels": {
            "sl": round(sl, 2) if sl != 0 else 0,
            "tp": round(tp, 2) if tp != 0 else 0
        },
        "data": {
            "gold": round(price, 2),
            "ema200": round(ema200, 2)
        }
    }

@app.route('/api/status', methods=['GET'])
def home():
    try:
        tf = request.args.get('interval', '5m')
        # Map to YFinance supported intervals
        valid_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", 
            "1H": "1h", "2H": "1h", "4H": "1h", "1D": "1d"
        }
        yf_tf = valid_map.get(tf, "5m")
        
        session_name, vol_mult = get_session_profile_dubai()
        
        data_pack = fetch_live_data(yf_tf)
        intel = calculate_logic(data_pack, session_name, vol_mult)
        
        response = {
            "timestamp": datetime.now().strftime("%H:%M:%S UTC"),
            "session": {"name": session_name},
            "engine": intel
        }
        
        resp = jsonify(response)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp
    except Exception as e:
        return jsonify({"engine": {"signal": "OFFLINE", "forecast": "Server Error", "probs": {"buy":0, "sell":0}, "lock": True}})

if __name__ == "__main__":
    app.run(debug=True)
