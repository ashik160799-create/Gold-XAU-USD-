from flask import Flask, jsonify, request
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np
import traceback

app = Flask(__name__)

# ==============================================================================
# 🚀 LEVEL-7+ "PURE INSTITUTIONAL" ENGINE (ULTIMATE PERFORMANCE)
# ==============================================================================

def get_session_profile_dubai():
    """Returns session name and volatility multiplier (Dubai UTC+4)."""
    utc_hour = datetime.utcnow().hour
    dubai_hour = (utc_hour + 4) % 24
    
    if 2 <= dubai_hour < 12: return "ASIAN (RANGE)", 0.7 
    if 12 <= dubai_hour < 17: return "LONDON (BREAKOUT)", 1.2
    if 17 <= dubai_hour < 21: return "OVERLAP (STRONGEST)", 1.6 
    if 21 <= dubai_hour < 23: return "NY (VOLATILE)", 1.4
    return "LATE NY (FADE)", 0.9

def calculate_technicals(df):
    """
    Calculates Level-7 Institutional Indicators (VSA + Smart Money).
    """
    try:
        if len(df) < 200:
            return None 
            
        # 1. EMAs (Institutional Trends)
        df['EMA_200'] = df['Close'].ewm(span=200, adjust=False).mean()
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
        
        # 2. RSI (Momentum Filter)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, 0.001)
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 3. ATR (Volatility for Exness Levels)
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['ATR'] = true_range.rolling(14).mean()

        # 4. VSA (Volume Spread Analysis) - Looking for Big Money
        df['Vol_Avg'] = df['Volume'].rolling(20).mean()
        df['VSA_Spike'] = df['Volume'] > (df['Vol_Avg'] * 1.5)
        
        # 5. Smart Money Expansion (Order Blocks)
        df['Body'] = (df['Close'] - df['Open']).abs()
        df['Range'] = df['High'] - df['Low']
        df['Is_Expansion'] = df['Body'] > (df['Range'].rolling(50).mean() * 1.8)

        return df
    except Exception as e:
        print(f"Technical Calc Error: {e}")
        return None

def fetch_live_data(interval):
    """
    Fetches REAL market data.
    """
    try:
        yf_interval = interval
        period = "60d" 
        
        if interval == "1m": period = "5d"
        elif interval == "5m": period = "60d"
        elif interval == "15m": period = "60d"
        elif interval == "1h": period = "1y"
        elif interval == "1d": period = "2y"

        tickers = ["GC=F", "DX-Y.NYB", "^TNX"]
        data = yf.download(tickers, period=period, interval=yf_interval, progress=False, group_by='ticker')
        
        response = {}
        if "GC=F" in data:
            gold_df = data["GC=F"].copy().dropna()
            gold_df = calculate_technicals(gold_df)
            response["GOLD_DF"] = gold_df
            response["GOLD_PRICE"] = gold_df['Close'].iloc[-1] if gold_df is not None else 0

        if "DX-Y.NYB" in data:
            response["DXY_SERIES"] = data["DX-Y.NYB"]['Close'].dropna().tail(21).values
        else: response["DXY_SERIES"] = []

        return response
    except Exception as e:
        print(f"Data Fetch Error: {e}")
        return None

def calculate_logic(data_pack, session_name, session_vol):
    """
    LEVEL-7+ INSTITUTIONAL ENGINE
    Specs: VSA Confirmation, Smart Money Expansion, Trend & Momentum.
    """
    if not data_pack or "GOLD_DF" not in data_pack or data_pack["GOLD_DF"] is None:
         return {"signal": "WAIT", "formatted_report": "System Offline", "lock": True}
    
    df = data_pack["GOLD_DF"]
    dxy_series = data_pack["DXY_SERIES"]
    
    current = df.iloc[-1]
    price = current['Close']
    
    # --- A. INSTITUTIONAL TREND ---
    ema200 = current['EMA_200']
    ema50 = current['EMA_50']
    ema21 = current['EMA_21']
    trend = "NEUTRAL"
    if price > ema200 and ema21 > ema50: trend = "BULLISH"
    elif price < ema200 and ema21 < ema50: trend = "BEARISH"
    
    # --- B. VSA & MOMENTUM ---
    vsa_confirm = current['VSA_Spike']
    is_expansion = current['Is_Expansion']
    rsi = current['RSI']
    
    # --- C. CORRELATION & SAFETY ---
    lock_reason = None
    is_locked = False
    if len(dxy_series) > 10:
        d_delta = abs(dxy_series[-1] - dxy_series[-2])
        if d_delta > 0.15: 
            is_locked = True
            lock_reason = "VOLATILITY SHOCK"
            
    # --- D. SCORING ENGINE (Level 7) ---
    score = 50
    if trend == "BULLISH": score += 20
    elif trend == "BEARISH": score -= 20
    
    if vsa_confirm:
        if current['Close'] > current['Open']: score += 10
        else: score -= 10
        
    if is_expansion:
        if current['Close'] > current['Open']: score += 10
        else: score -= 10
        
    if rsi > 58: score += 10
    elif rsi < 42: score -= 10
    
    score = 50 + ((score - 50) * session_vol)
    
    # --- E. FINAL SIGNAL & EXNESS LEVELS (SIMPLIFIED) ---
    buy_prob = int(score)
    sell_prob = int(100 - score)
    signal = "WAIT"
    sl = tp = 0.0
    atr = current['ATR']
    
    if is_locked:
        signal = "WAIT"
    else:
        # Simplified Decisive Rules
        if buy_prob >= 65 and trend == "BULLISH":
            signal = "BUY"
            sl = price - (1.5 * atr)
            tp = price + (3.0 * atr) 
        elif sell_prob >= 65 and trend == "BEARISH":
            signal = "SELL"
            sl = price + (1.5 * atr)
            tp = price - (3.0 * atr)
        else:
            signal = "WAIT"
            
    # --- F. PREDICTIVE FORECAST (SIMPLIFIED) ---
    forecast = "WAIT"
    if signal == "BUY":
        forecast = "BUY"
    elif signal == "SELL":
        forecast = "SELL"
    else:
        forecast = "WAIT"

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
    tf = request.args.get('interval', '5m')
    valid_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1H": "1h", "4H": "1h", "1D": "1d"}
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

if __name__ == "__main__":
    app.run(debug=True)
