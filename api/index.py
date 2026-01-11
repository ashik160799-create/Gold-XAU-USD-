from flask import Flask, jsonify, request
from datetime import datetime
import yfinance as yf
import traceback

app = Flask(__name__)

# ==============================================================================
# 🚀 LEVEL-9 "PURE INSTITUTIONAL" ENGINE (MTA + YIELD CORRELATION)
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
    Fetches REAL market data for requested interval and 1H for MTA.
    """
    try:
        yf_interval = interval
        period = "60d" 
        
        if interval == "1h": period = "1y"
        elif interval == "1d": period = "2y"

        tickers = ["GC=F", "DX-Y.NYB", "^TNX"]
        
        # Download data
        data = yf.download(tickers, period=period, interval=yf_interval, progress=False, group_by='ticker')
        
        # Fetch 1H data for MTA if current interval is smaller
        mta_data = None
        if yf_interval in ["1m", "5m", "15m"]:
            mta_data = yf.download("GC=F", period="1y", interval="1h", progress=False)

        response = {}
        
        # Process Gold
        if "GC=F" in data:
            df = data["GC=F"].dropna()
            response["OPENS"] = df['Open'].tolist()
            response["HIGHS"] = df['High'].tolist()
            response["LOWS"] = df['Low'].tolist()
            response["CLOSES"] = df['Close'].tolist()
            response["VOLUMES"] = df['Volume'].tolist()

        # Process DXY
        if "DX-Y.NYB" in data:
            response["DXY_CLOSES"] = data["DX-Y.NYB"]['Close'].dropna().tolist()
        else:
            response["DXY_CLOSES"] = []

        # Process Yields (^TNX)
        if "^TNX" in data:
            response["YIELD_CLOSES"] = data["^TNX"]['Close'].dropna().tolist()
        else:
            response["YIELD_CLOSES"] = []

        # Process MTA (1H Gold)
        if mta_data is not None and not mta_data.empty:
            response["MTA_1H_CLOSES"] = mta_data['Close'].dropna().tolist()
        else:
            response["MTA_1H_CLOSES"] = []

        return response
    except Exception as e:
        print(f"Data Fetch Error: {e}")
        return None

def detect_liquidity_grab(highs, lows, closes, opens):
    """
    Detects stop-runs/liquidity grabs: Wicks that sweep previous highs/lows and reject.
    """
    if len(closes) < 5: return "NONE"
    
    curr_h = highs[-1]
    curr_l = lows[-1]
    curr_c = closes[-1]
    curr_o = opens[-1]
    
    # Previous swing high/low (simple 3-candle)
    prev_h = max(highs[-4:-1])
    prev_l = min(lows[-4:-1])
    
    # Bearish Grab: Price sweeps prev high then closes back below it
    if curr_h > prev_h and curr_c < prev_h and curr_c < curr_o:
        return "BEARISH_GRAB"
    
    # Bullish Grab: Price sweeps prev low then closes back above it
    if curr_l < prev_l and curr_c > prev_l and curr_c > curr_o:
        return "BULLISH_GRAB"
        
    return "NONE"

def calculate_logic(data_pack, session_name, session_vol):
    """
    LEVEL-9 ENGINE (MTA + Yield Correlation + Liquidity Grabs)
    """
    if not data_pack or "CLOSES" not in data_pack or len(data_pack["CLOSES"]) < 200:
         return {"signal": "WAIT", "formatted_report": "System Offline", "lock": True}
    
    closes = data_pack["CLOSES"]
    opens = data_pack["OPENS"]
    highs = data_pack["HIGHS"]
    lows = data_pack["LOWS"]
    volumes = data_pack["VOLUMES"]
    dxy_series = data_pack["DXY_CLOSES"]
    yield_series = data_pack.get("YIELD_CLOSES", [])
    mta_1h = data_pack.get("MTA_1H_CLOSES", [])
    
    # Current Candle
    price = closes[-1]
    
    # --- A. INSTITUTIONAL TREND (EMA) ---
    ema200 = calculate_ema(closes, 200)
    ema50 = calculate_ema(closes, 50)
    ema21 = calculate_ema(closes, 21)
    
    trend = "NEUTRAL"
    if price > ema200 and ema21 > ema50: trend = "BULLISH"
    elif price < ema200 and ema21 < ema50: trend = "BEARISH"
    
    # --- B. MULTI-TIMEFRAME ALIGNMENT (MTA) ---
    mta_trend = "NEUTRAL"
    if len(mta_1h) >= 200:
        ema200_1h = calculate_ema(mta_1h, 200)
        if mta_1h[-1] > ema200_1h: mta_trend = "BULLISH"
        else: mta_trend = "BEARISH"
    
    # --- C. VSA & LIQUIDITY ---
    vol_avg = sum(volumes[-21:-1]) / 20 if len(volumes) > 20 else 1
    vsa_confirm = volumes[-1] > (vol_avg * 1.5)
    
    liq_grab = detect_liquidity_grab(highs, lows, closes, opens)
    
    # Expansion
    body = abs(closes[-1] - opens[-1])
    ranges = [(h-l) for h, l in zip(highs[-51:-1], lows[-51:-1])]
    avg_range = sum(ranges) / len(ranges) if ranges else 1
    is_expansion = body > (avg_range * 1.8)
    
    rsi = calculate_rsi(closes, 14)
    
    # --- D. CORRELATION (DXY & YIELD) ---
    lock_reason = None
    is_locked = False
    
    # DXY Shock
    if len(dxy_series) > 10:
        d_delta = abs(dxy_series[-1] - dxy_series[-2])
        if d_delta > 0.15: 
            is_locked = True
            lock_reason = "DXY VOLATILITY"
            
    # Yield Correlation (Inverse)
    yield_bias = "NEUTRAL"
    if len(yield_series) > 10:
        y_change = yield_series[-1] - yield_series[-5]
        if y_change > 0.05: yield_bias = "BEARISH" # Yields UP = Gold DOWN
        elif y_change < -0.05: yield_bias = "BULLISH" # Yields DOWN = Gold UP
            
    # --- E. SCORING ENGINE ---
    score = 50
    if trend == "BULLISH": score += 15
    elif trend == "BEARISH": score -= 15
    
    if mta_trend == trend: score += 10 if trend == "BULLISH" else -10
    
    if yield_bias == "BULLISH": score += 10
    elif yield_bias == "BEARISH": score -= 10
    
    if vsa_confirm:
        if closes[-1] > opens[-1]: score += 10
        else: score -= 10
        
    if is_expansion:
        if closes[-1] > opens[-1]: score += 10
        else: score -= 10
        
    if liq_grab == "BULLISH_GRAB": score += 15
    elif liq_grab == "BEARISH_GRAB": score -= 15
        
    if rsi > 58: score += 10
    elif rsi < 42: score -= 10
    
    # Session weight
    score = 50 + ((score - 50) * session_vol)
    
    # --- F. FINAL SIGNAL & EXNESS LEVELS ---
    buy_prob = max(0, min(100, int(score)))
    sell_prob = 100 - buy_prob
    signal = "WAIT"
    sl = tp = 0.0
    atr = calculate_atr(highs, lows, closes, 14)
    
    if is_locked:
        signal = f"WAIT ({lock_reason})"
    else:
        # High Probability Confluence
        if buy_prob >= 75 and mta_trend == "BULLISH":
            signal = "STRONG BUY"
            sl = price - (2.2 * atr)
            tp = price + (3.8 * atr) 
        elif sell_prob >= 75 and mta_trend == "BEARISH":
            signal = "STRONG SELL"
            sl = price + (2.2 * atr)
            tp = price - (3.8 * atr)
        elif buy_prob >= 65:
            signal = "BUY"
            sl = price - (1.6 * atr)
            tp = price + (2.8 * atr)
        elif sell_prob >= 65:
            signal = "SELL"
            sl = price + (1.6 * atr)
            tp = price - (2.8 * atr)
            
    # --- G. PREDICTIVE FORECAST ---
    forecast = "NEUTRAL (WAIT)"
    if signal.startswith("STRONG"):
        forecast = "INSTITUTIONAL RALLY (CONTINUE)" if "BUY" in signal else "INSTITUTIONAL DUMP (CONTINUE)"
    elif mta_trend == trend and trend != "NEUTRAL":
        forecast = "MULTI-TIMEFRAME CONFLUENCE"
    elif liq_grab != "NONE":
        forecast = "LIQUIDITY REVERSAL DETECTED"
    elif "BUY" in signal and yield_bias == "BULLISH":
        forecast = "YIELD-SUPPORTED UPSIDE"
    elif "SELL" in signal and yield_bias == "BEARISH":
        forecast = "YIELD-SUPPORTED DOWNSIDE"
    elif is_locked:
        forecast = "STAY OUT (DANGEROUS)"
    else:
        forecast = "CONSOLIDATION (WAIT)"

    return {
        "signal": signal,
        "forecast": forecast,
        "probs": {"buy": buy_prob, "sell": sell_prob},
        "trend": trend,
        "mta": mta_trend,
        "yield_bias": yield_bias,
        "rsi": round(rsi, 1),
        "vsa": "BIG MONEY" if vsa_confirm else "NORMAL",
        "liq_grab": liq_grab,
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
