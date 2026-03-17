import yfinance as yf
from datetime import datetime

# Test NIFTY data fetching
print("Testing Yahoo Finance NIFTY data...")
nifty = yf.Ticker("^NSEI")

# Get current price
data = nifty.history(period="1d")
if not data.empty:
    current_price = float(data['Close'].iloc[-1])
    print(f"✅ Current NIFTY Price: ₹{current_price:.2f}")
else:
    print("❌ No current price data")

# Get historical data for pivots
hist_data = nifty.history(period="5d")
if len(hist_data) >= 2:
    prev_day = hist_data.iloc[-2]
    print(f"\n✅ Previous Day Data:")
    print(f"   Open:  ₹{float(prev_day['Open']):.2f}")
    print(f"   High:  ₹{float(prev_day['High']):.2f}")
    print(f"   Low:   ₹{float(prev_day['Low']):.2f}")
    print(f"   Close: ₹{float(prev_day['Close']):.2f}")
    
    # Calculate pivot
    prev_high = float(prev_day['High'])
    prev_low = float(prev_day['Low'])
    prev_close = float(prev_day['Close'])
    pivot = (prev_high + prev_low + prev_close) / 3
    print(f"\n✅ Calculated Pivot: ₹{pivot:.2f}")
else:
    print("❌ Insufficient historical data")
