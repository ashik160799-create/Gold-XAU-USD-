from flask import Flask, jsonify, request, send_from_directory
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd
import numpy as np
import traceback
import os

# Point to 'public' folder for static files
app = Flask(__name__, static_folder='../public')

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

# ==============================================================================
# 🚀 GOLD INTELLIGENCE "LEVEL-9" ENGINE (STRATEGY UPGRADE)
# ==============================================================================

# --- INDICATORS ---

def calculate_indicators(df):
    """Calculates all technical indicators including Stoch, VWAP, EMA Layers."""
    if df.empty: return df

    # 1. EMA LAYERS (Trend)
    df['EMA5'] = df['Close'].ewm(span=5, adjust=False).mean()
    df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()

    # 2. MOMENTUM TRIO
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
    df['MACD_Hist'] = df['MACD'] - df['Signal_Line']

    # Stochastic (K%D)
    low_min = df['Low'].rolling(window=14).min()
    high_max = df['High'].rolling(window=14).max()
    df['Stoch_K'] = 100 * ((df['Close'] - low_min) / (high_max - low_min))
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()

    # 3. VOLATILITY & VWAP
    # ATR
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    # Anchored VWAP Approximation (Session start based on index usually)
    # Simple VWAP (Volume Weighted Average Price) over rolling window as proxy if session not cut
    v = df['Volume']
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    df['VWAP'] = (tp * v).rolling(window=30).sum() / v.rolling(window=30).sum()

    # 4. PATTERNS & ACCELERATION
    df['Delta'] = df['Close'].diff()
    df['DeltaDelta'] = df['Delta'].diff()

    return df

# --- HELPERS ---

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
        
def get_htf_trend(data_store, current_tf):
    """Determines High Time Frame trend for confirmation."""
    htf_map = {
        '1M': '15m', '5M': '1h', '15M': '4h', 
        '1H': '4h', '2H': '1d', '4H': '1d', '1D': '1wk'
    }
    target_htf = htf_map.get(current_tf.upper(), None)
    if not target_htf: return "NEUTRAL"
    
    # normalize key
    key = target_htf.lower()
    if key not in data_store: return "NEUTRAL"
    
    htf_df = data_store[key]
    if htf_df is None or len(htf_df) < 50: return "NEUTRAL"
    
    # Simple HTF Logic: EMA 50 Slope or Position
    # Assume calculcated already or calc now
    if 'EMA50' not in htf_df.columns:
         htf_df = calculate_indicators(htf_df)
         
    last = htf_df.iloc[-1]
    
    if last['Close'] > last['EMA50']: return "BULLISH"
    if last['Close'] < last['EMA50']: return "BEARISH"
    return "NEUTRAL"

def detect_wick_anomaly(df):
    """Advanced Wick Detection (2x avg of last 10)."""
    if len(df) < 15: return False, ""
    
    last = df.iloc[-1]
    
    # Avg Wick Size
    past_10 = df.iloc[-11:-1]
    # Handle bodies
    p_high = past_10['High']
    p_low = past_10['Low']
    p_open = past_10['Open']
    p_close = past_10['Close']
    
    # Upper Wick = High - Max(Open, Close)
    avg_upper_wick = (p_high - pd.DataFrame({'a': p_open, 'b': p_close}).max(axis=1)).mean()
    # Lower Wick = Min(Open, Close) - Low
    avg_lower_wick = (pd.DataFrame({'a': p_open, 'b': p_close}).min(axis=1) - p_low).mean()
    
    curr_upper = last['High'] - max(last['Open'], last['Close'])
    curr_lower = min(last['Open'], last['Close']) - last['Low']
    atr = last['ATR'] if not pd.isna(last['ATR']) else 0
    
    if curr_upper > (avg_upper_wick * 2.5) and curr_upper > atr * 0.5:
        return True, "BEARISH REJECTION"
    if curr_lower > (avg_lower_wick * 2.5) and curr_lower > atr * 0.5:
        return True, "BULLISH REJECTION"
        
    return False, ""

# --- CORE LOGIC ENGINE ---

def analyze_timeframe(tf, df, data_store):
    """
    Level-9 Analysis Engine.
    """
    if df is None or df.empty or len(df) < 50:
         return {
             "timeframe": tf.upper(), 
             "action": "WAIT", 
             "confidence": "0%", 
             "reason": "Insufficient Data", 
             "signal": "WAIT", 
             "raw_signal": "signal-wait",
             "trade_guide": {"entry": "-", "sl": "-", "tp": "-"},
             "score": 0,
             "description": "Fetching market data..."
         }

    # Run Indicators
    df = calculate_indicators(df)
    last = df.iloc[-1]
    atr = last['ATR'] if not pd.isna(last['ATR']) else 0
    
    # DXY Context
    dxy_df = data_store.get('dxy_1h')
    
    score = 0
    reasons = []
    
    # 1. MULTI-LAYER TREND
    bull_layers = 0
    bear_layers = 0
    
    # L1: Short
    if last['EMA5'] > last['EMA20']: bull_layers += 1
    elif last['EMA5'] < last['EMA20']: bear_layers += 1
    
    # L2: Medium
    if last['EMA20'] > last['EMA50']: bull_layers += 1
    elif last['EMA20'] < last['EMA50']: bear_layers += 1
    
    # L3: Long
    if not pd.isna(last['EMA200']):
        if last['EMA50'] > last['EMA200']: bull_layers += 1
        elif last['EMA50'] < last['EMA200']: bear_layers += 1

    if bull_layers == 3: score += 40; reasons.append("Full Bull Trend")
    elif bear_layers == 3: score -= 40; reasons.append("Full Bear Trend")
    elif bull_layers >= 2: score += 20; reasons.append("Bull Bias")
    elif bear_layers >= 2: score -= 20; reasons.append("Bear Bias")
    else: reasons.append("Trend Mixed")
    
    # 2. MOMENTUM TRIO (RSI, Stoch, MACD)
    mom_bull = 0
    mom_bear = 0
    
    # RSI
    if last['RSI'] > 55: mom_bull += 1
    elif last['RSI'] < 45: mom_bear += 1
    
    # Stoch
    if not pd.isna(last['Stoch_K']):
        if last['Stoch_K'] > last['Stoch_D'] and last['Stoch_K'] < 80: mom_bull += 1
        elif last['Stoch_K'] < last['Stoch_D'] and last['Stoch_K'] > 20: mom_bear += 1
    
    # MACD
    if last['MACD'] > last['Signal_Line']: mom_bull += 1
    else: mom_bear += 1
    
    if mom_bull >= 2: score += 25; reasons.append("Mom Strong (+)")
    elif mom_bear >= 2: score -= 25; reasons.append("Mom Strong (-)")
    
    # 3. HTF CONFIRMATION
    htf_trend = get_htf_trend(data_store, tf)
    if score > 0 and htf_trend == "BULLISH": score += 15
    elif score < 0 and htf_trend == "BEARISH": score -= 15
    elif score > 0 and htf_trend == "BEARISH": score -= 15; reasons.append("HTF Conflict")
    elif score < 0 and htf_trend == "BULLISH": score += 15; reasons.append("HTF Conflict")

    # 4. VOLATILITY & STOP HUNT
    is_wick, wick_type = detect_wick_anomaly(df)
    if is_wick:
        reasons.append(f"⚠️ {wick_type}")
        if "BULLISH" in wick_type: score += 15 # Reversal Buy
        if "BEARISH" in wick_type: score -= 15 # Reversal Sell
    
    # Check for Massive ATR Spike (News proxy) - Wait
    body = abs(last['Close'] - last['Open'])
    if body > 3 * atr and atr > 0:
        score = 0 # Force Wait
        reasons.append("Extreme Volatility (News?)")

    # 5. DXY CORRELATION
    if dxy_df is not None:
        dxy_last = dxy_df.iloc[-1]
        dxy_up = dxy_last['Close'] > dxy_last['Open']
        gold_up = last['Close'] > last['Open']
        if dxy_up and gold_up:
            score *= 0.7 # Reduce confidence
            reasons.append("DXY Correlation Risk")
        elif not dxy_up and not gold_up:
            score *= 0.7
            reasons.append("DXY Correlation Risk")

    # --- FINAL DECISION ---
    action = "WAIT"
    confidence = 50
    display_score = 50 + (score / 1.6) # Scale
    display_score = max(0, min(100, int(display_score)))
    
    if display_score >= 65: action = "BUY"
    elif display_score <= 35: action = "SELL"
    else: action = "WAIT"

    # Trade Guidance
    if atr > 0:
        current_price = last['Close']
        sl = 0
        tp = 0
        if action == "BUY":
            sl = current_price - (1.5 * atr)
            tp = current_price + (2.0 * atr)
        elif action == "SELL":
            sl = current_price + (1.5 * atr)
            tp = current_price - (2.0 * atr)
            
        trade_guide = {
            "entry": f"{current_price:.2f}",
            "sl": f"{sl:.2f}",
            "tp": f"{tp:.2f}"
        }
    else:
        trade_guide = {"entry": "-", "sl": "-", "tp": "-"}
        
    # Wait Logic Override
    if action == "WAIT":
         trade_guide = {"entry": "-", "sl": "-", "tp": "-"}

    final_reason = ", ".join(reasons)

    return {
        "timeframe": tf.upper(),
        "action": action,
        "confidence": f"{display_score}%",
        "reason": final_reason,
        "score": display_score,
        "signal": action,
        "description": final_reason,
        "trade_guide": trade_guide,
        "raw_signal": "signal-buy" if action == "BUY" else "signal-sell" if action == "SELL" else "signal-wait"
    }

# --- DATA FETCHING ---

def fetch_all_timeframes():
    """Fetches and prepares data for Gold and DXY for all timeframes."""
    data_store = {}
    gold_tickers = ["GC=F", "XAUUSD=X"]
    dxy_tickers = ["DX-Y.NYB", "^DXY"]
    
    # --- FETCH GOLD ---
    for ticker in gold_tickers:
        print(f"DEBUG: Attempting to fetch Gold data from {ticker}...")
        try:
            df_intra = yf.download(ticker, period="5d", interval="1m", progress=False, timeout=20)
            df_hourly = yf.download(ticker, period="60d", interval="1h", progress=False, timeout=20)
            df_daily = yf.download(ticker, period="2y", interval="1d", progress=False, timeout=20)
            df_weekly = yf.download(ticker, period="2y", interval="1wk", progress=False, timeout=20)

            def validate_df(df):
                if df is None or df.empty: return False
                if isinstance(df.columns, pd.MultiIndex):
                    try: df = df.xs(ticker, level=0, axis=1)
                    except: 
                        try: df = df.xs(ticker, level=1, axis=1)
                        except: return False
                
                col_map = {c.lower(): c for c in df.columns}
                if 'close' not in col_map and 'adj close' in col_map:
                    df['Close'] = df[col_map['adj close']]
                elif 'close' not in col_map:
                    return False
                
                # Check for NaNs in Close
                if df['Close'].isnull().all(): return False
                    
                df = df.dropna(subset=['Close'])
                return df if len(df) > 10 else False

            # Validate Main Data source
            valid_hourly = validate_df(df_hourly)
            
            if valid_hourly is not False:
                # Process All
                data_store['1h'] = valid_hourly
                data_store['1d'] = validate_df(df_daily)
                data_store['1wk'] = validate_df(df_weekly)
                
                # Resampling
                valid_intra = validate_df(df_intra)
                if valid_intra is not False:
                    logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
                    # Fix: Ensure Volume exists
                    if 'Volume' not in valid_intra.columns: valid_intra['Volume'] = 0
                    
                    data_store['1m'] = valid_intra
                    data_store['5m'] = valid_intra.resample('5min').agg(logic).dropna()
                    data_store['15m'] = valid_intra.resample('15min').agg(logic).dropna()
                else:
                    # Fallback
                    data_store['5m'] = validate_df(yf.download(ticker, period="5d", interval="5m", progress=False))
                    data_store['15m'] = validate_df(yf.download(ticker, period="5d", interval="15m", progress=False))
                
                # 4H Resampling
                logic_h = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
                if 'Volume' not in valid_hourly.columns: valid_hourly['Volume'] = 0
                
                data_store['2h'] = valid_hourly.resample('2h').agg(logic_h).dropna()
                data_store['4h'] = valid_hourly.resample('4h').agg(logic_h).dropna()
                
                break 
        except Exception as e:
            print(f"DEBUG: Gold fetch failed for {ticker}: {e}")
            continue

    # --- FETCH DXY ---
    for ticker in dxy_tickers:
        try:
             dxy_df = yf.download(ticker, period="60d", interval="1h", progress=False)
             if dxy_df is None or dxy_df.empty: continue
             if isinstance(dxy_df.columns, pd.MultiIndex):
                 try: dxy_df = dxy_df.xs(ticker, level=0, axis=1)
                 except: continue
             data_store['dxy_1h'] = dxy_df
             break
        except: continue
             
    return data_store

@app.route('/api/dashboard', methods=['GET'])
def dashboard():
    try:
        data_store = fetch_all_timeframes()
        results = []
        ordered_tfs = ["1m", "5m", "15m", "1h", "2h", "4h", "1d", "1wk"]
        
        for tf in ordered_tfs:
            df = data_store.get(tf) # keys are lowercase or matched? check fetch logic
            # fetch logic keys: '1h', '1d', '1wk', '1m', '5m', '15m', '2h', '4h' -> All lowercase
            # ordered_tfs are consistent.
            
            result = analyze_timeframe(tf, df, data_store) 
            results.append(result)
            
        session, _ = get_session_profile_dubai()
        
        return jsonify({
            "timestamp": datetime.now().strftime("%H:%M:%S UTC"),
            "session": session,
            "signals": results
        })

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e), "signals": []})

@app.route('/api/status', methods=['GET'])
def home():
    return jsonify({"message": "GoldIntelligence Level-9 Active"})

if __name__ == "__main__":
    app.run(debug=True)
