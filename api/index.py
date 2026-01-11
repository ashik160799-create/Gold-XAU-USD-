from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np
import traceback

app = Flask(__name__)

# ==============================================================================
# 🚀 LEVEL-9 "DECISION ENGINE" (MULTI-TIMEFRAME + WEIGHTED SCORING)
# ==============================================================================

TIMEFRAMES = ["1m", "5m", "15m", "1h", "2h", "4h", "1d", "1wk"]

MIN_HISTORY = 100  # Minimum candles required for accurate indicators

def get_session_profile_dubai():
    """Returns session name and volatility multiplier (Dubai UTC+4)."""
    try:
        utc_now = datetime.utcnow()
        utc_hour = utc_now.hour
        dubai_hour = (utc_hour + 4) % 24
        
        if 2 <= dubai_hour < 12: return "ASIAN (RANGE)", 0.7 
        if 12 <= dubai_hour < 17: return "LONDON (BREAKOUT)", 1.2
        if 17 <= dubai_hour < 21: return "OVERLAP (STRONGEST)", 1.6 
        if 21 <= dubai_hour < 23: return "NY (VOLATILE)", 1.4
        return "LATE NY (FADE)", 0.9
    except:
        return "MARKET", 1.0

# --- PANDAS INDICATORS ---

def calculate_indicators(df):
    """Calculates technical indicators on a DataFrame."""
    if df.empty: return df

    # EMA
    df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()

    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # Bollinger Bands
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['STD20'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['SMA20'] + (df['STD20'] * 2)
    df['BB_Lower'] = df['SMA20'] - (df['STD20'] * 2)

    # ATR
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()

    return df

def fetch_all_timeframes():
    """Fetches and prepares data for all 8 timeframes."""
    data_store = {}
    
    # 1. Fetch Standard Timeframes directly
    # Use XAUUSD=X (Spot Gold) instead of futures for better Forex alignment
    ticker = "XAUUSD=X"
    
    # Group 1: Intraday
    tickers_intraday = yf.download(ticker, period="5d", interval="1m", progress=False) # 1m
    tickers_5m = yf.download(ticker, period="5d", interval="5m", progress=False) # 5m
    tickers_15m = yf.download(ticker, period="5d", interval="15m", progress=False) # 15m
    
    # Group 2: Hourly/Swing (Source for 2H/4H)
    tickers_1h = yf.download(ticker, period="1y", interval="1h", progress=False) # 1h
    
    # Group 3: Daily/Weekly
    tickers_1d = yf.download(ticker, period="2y", interval="1d", progress=False) # 1d
    tickers_1wk = yf.download(ticker, period="2y", interval="1wk", progress=False) # 1wk
    
    # Store accessible dfs
    def process_yf(df):
        if df is None or df.empty: return None
        
        # Handle MultiIndex if present (common in new yfinance 0.2.x+)
        if isinstance(df.columns, pd.MultiIndex):
            # Check if ticker is in level 1 (common) or level 0
            try:
                if ticker in df.columns.levels[1]: # Columns: (Price, Ticker)
                     df = df.xs(ticker, level=1, axis=1)
                elif ticker in df.columns.levels[0]: # Columns: (Ticker, Price)
                     df = df.xs(ticker, level=0, axis=1)
            except:
                pass # structure might be simple
            
            # If still MultiIndex, fallback to level 0
            if isinstance(df.columns, pd.MultiIndex):
                 df.columns = df.columns.get_level_values(0)

        # Ensure we have required columns
        # sometimes yfinance returns 'Adj Close' but not 'Close' or vice versa
        if 'Close' not in df.columns and 'Adj Close' in df.columns:
            df['Close'] = df['Adj Close']
            
        req = ['Open', 'High', 'Low', 'Close', 'Volume']
        if not all(col in df.columns for col in req):
            # Try to find columns case-insensitively
            found_cols = {}
            for r in req:
                for c in df.columns:
                    if str(c).lower() == r.lower():
                        found_cols[r] = c
            
            if len(found_cols) == len(req):
                df = df.rename(columns={v: k for k, v in found_cols.items()})
            else:
                return None
        
        # Drop any NaN rows that might break calculations
        df = df.dropna(subset=['Close'])
        return df

    data_store['1m'] = process_yf(tickers_intraday)
    data_store['5m'] = process_yf(tickers_5m)
    data_store['15m'] = process_yf(tickers_15m)
    data_store['1h'] = process_yf(tickers_1h)
    data_store['1d'] = process_yf(tickers_1d)
    data_store['1wk'] = process_yf(tickers_1wk)

    # Resampling for 2H and 4H
    if data_store['1h'] is not None:
        logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
        data_store['2h'] = data_store['1h'].resample('2h').agg(logic).dropna()
        data_store['4h'] = data_store['1h'].resample('4h').agg(logic).dropna()

    return data_store

def analyze_timeframe(tf, df):
    """Generates signal and description for a specific timeframe."""
    if df is None:
         return {"timeframe": tf.upper(), "signal": "WAIT", "description": "Data Fetch Failed (Empty)", "color": "text-muted"}
         
    if len(df) < 5: # bare minimum
         return {"timeframe": tf.upper(), "signal": "WAIT", "description": f"Insufficient Data (Rows: {len(df)})", "color": "text-muted"}

    # Run Indicators
    df = calculate_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]

    # --- SCORING ENGINE ---
    score = 50
    reasons = []

    # 1. Trend (40%)
    trend_score = 0
    if last['Close'] > last['EMA200']: trend_score += 10
    else: trend_score -= 10
    
    if last['EMA21'] > last['EMA50']: 
        trend_score += 10
        reasons.append("Bullish Trend")
    elif last['EMA21'] < last['EMA50']:
        trend_score -= 10
        reasons.append("Bearish Trend")
    else:
        reasons.append("Trend Neutral")

    score += trend_score

    # 2. Momentum (30%)
    mom_score = 0
    # RSI
    if last['RSI'] > 55: mom_score += 5
    elif last['RSI'] < 45: mom_score -= 5
    
    # MACD
    if last['MACD'] > last['Signal_Line']: mom_score += 10; reasons.append("MACD Bullish")
    else: mom_score -= 10; reasons.append("MACD Bearish")

    score += mom_score

    # 3. Volatility/PA (30%)
    vol_score = 0
    # BB Expansion
    bb_width = last['BB_Upper'] - last['BB_Lower']
    prev_bb_width = prev['BB_Upper'] - prev['BB_Lower']
    if bb_width > prev_bb_width * 1.1: reasons.append("Vol Expanding")
    
    # Price vs BB
    if last['Close'] > last['BB_Upper']: vol_score += 10
    elif last['Close'] < last['BB_Lower']: vol_score -= 10

    score += vol_score

    # --- SIGNAL GENERATION ---
    signal = "WAIT"
    color = "text-yellow-500" # Tailwind class concept or CSS var
    
    if score >= 65:
        signal = "BUY"
        color = "signal-buy"
    elif score <= 35:
        signal = "SELL"
        color = "signal-sell"
    else:
        signal = "WAIT"
        color = "signal-wait"

    # Construct Description
    # "Uptrend strong, EMA21>EMA50, RSI 62"
    desc_parts = []
    
    # Trend Desc
    if last['Close'] > last['EMA200']: desc_parts.append("Uptrend")
    else: desc_parts.append("Downtrend")
    
    # Key Factors
    desc_parts.append(f"RSI {int(last['RSI'])}")
    if last['MACD'] > last['Signal_Line']: desc_parts.append("MACD +")
    else: desc_parts.append("MACD -")

    # Merge reasons for detail if needed, but keep short for UI
    final_desc = ", ".join(desc_parts)

    return {
        "timeframe": tf.upper(),
        "signal": signal,
        "description": final_desc,
        "score": score,
        "raw_signal": color # For UI styling
    }

@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    try:
        data_store = fetch_all_timeframes()
        results = []
        
        ordered_tfs = ["1m", "5m", "15m", "1h", "2h", "4h", "1d", "1wk"]
        
        for tf in ordered_tfs:
            df = data_store.get(tf)
            result = analyze_timeframe(tf, df)
            results.append(result)
            
        session, _ = get_session_profile_dubai()
        
        response = {
            "timestamp": datetime.now().strftime("%H:%M:%S UTC"),
            "session": session,
            "signals": results
        }
        
        resp = jsonify(response)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e), "signals": []})

@app.route('/api/status', methods=['GET']) # Keep old endpoint for backwards compatibility if needed
def home():
    # Redirect logic or simple fallback
    return jsonify({"message": "Use /api/dashboard for Level-9 Engine"})

if __name__ == "__main__":
    app.run(debug=True)
