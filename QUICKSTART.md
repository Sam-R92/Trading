# Traderchamp - Quick Start Guide

## 🚀 Installation

1. **Setup environment:**
   ```powershell
   .\setup.ps1
   ```

2. **Configure brokers:**
   - Copy `.env.example` to `.env`
   - Add your broker credentials

3. **Run application:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   python traderchamp.py
   ```

## 📋 Features

### 1️⃣ Quick Order
Fast order placement with 8-step interface:
1. Select Index (NIFTY/BANKNIFTY/SENSEX/FINNIFTY)
2. Select Expiry (next 4 weekly expiries)
3. Enter Strike Price
4. Select CE/PE
5. Select BUY/SELL
6. Enter Quantity (auto-detects lots vs contracts)
7. Select Order Type (MARKET/LIMIT)
8. Select Product (Intraday/Delivery)

**Smart Quantity Detection:**
- Input 1-10: Treated as lots (multiplied by lot size)
- Input >10: Treated as contracts (exact quantity)

Example:
- Input "2" for NIFTY = 50 contracts (2 × 25)
- Input "50" for NIFTY = 50 contracts

### 2️⃣ Increase Position
Add quantity to existing open position:
- Select position from list
- Enter quantity to add
- Confirms with order placement

### 3️⃣ Exit Position
Close positions completely:
- Exit specific position
- Exit ALL positions at once
- Market orders for instant execution

### 4️⃣ Partial Exit
Exit partial quantity from position:
- Select position
- Enter quantity to exit (must be ≤ current position)
- Remaining position stays open

### 5️⃣ View Positions
Display all open positions with:
- Symbol and quantity
- Real-time P&L (color-coded: 🟢/🔴)
- Total P&L calculation

### 6️⃣ View Portfolio
Portfolio summary showing:
- Available funds
- Used margin
- Today's P&L
- Holdings count
- Open positions count

### 7️⃣ Switch Broker
Change between Upstox and Dhan without restarting

## 🔧 Broker Configuration

### Upstox
1. Get API credentials from [Upstox Developer Console](https://api.upstox.com)
2. Generate access token (valid 24 hours)
3. Add to `.env`:
   ```env
   UPSTOX_API_KEY=your_api_key
   UPSTOX_API_SECRET=your_api_secret
   UPSTOX_ACCESS_TOKEN=your_access_token
   UPSTOX_ACCOUNT_NAME=YourName
   ```

### Dhan
1. Get access token from [Dhan API Portal](https://myaccount.dhan.co/api-tokens)
2. Add to `.env`:
   ```env
   DHAN_CLIENT_ID=your_client_id
   DHAN_ACCESS_TOKEN=your_access_token
   DHAN_ACCOUNT_NAME=YourName
   ```

## 📊 Supported Indices

| Index | Lot Size | Exchange |
|-------|----------|----------|
| NIFTY | 25 | NSE |
| BANKNIFTY | 15 | NSE |
| SENSEX | 10 | BSE |
| FINNIFTY | 40 | NSE |

## ⚡ Tips

1. **Order Types:**
   - MARKET: Instant execution at current price
   - LIMIT: Execute only at specified price or better

2. **Product Types:**
   - Intraday (MIS): Must square off before market close
   - Delivery (NRML): Can hold overnight

3. **Quantity Input:**
   - For small quantities (1-10): System treats as lots
   - For larger quantities (>10): System treats as exact contracts

4. **Quick Exit:**
   - Use "Exit Position" → "ALL" to close all positions instantly
   - Use "Partial Exit" to book profits on partial quantity

## 🛡️ Safety Features

- ✅ Order confirmation required before execution
- ✅ Clear order summary before placement
- ✅ Real-time P&L display with color coding
- ✅ Quantity validation (prevent over-exit)
- ✅ Error handling with descriptive messages

## 📁 Project Structure

```
Traderchamp/
├── traderchamp.py          # Main application
├── brokers/
│   ├── base_broker.py      # Abstract broker interface
│   ├── upstox_client.py    # Upstox implementation
│   └── dhan_client.py      # Dhan implementation
├── config/                 # Token storage
├── .env                    # Credentials (not in git)
├── setup.ps1              # Setup script
└── README.md              # Documentation
```

## 🐛 Troubleshooting

**Error: "Access token not set"**
- Check `.env` file has correct token
- Upstox tokens expire after 24 hours - regenerate if needed

**Error: "No broker selected"**
- Run option 7 to select broker first
- Verify credentials in `.env` file

**Orders not executing**
- Check available funds in portfolio
- Verify market hours (9:15 AM - 3:30 PM IST)
- Check if instrument key is valid

## 📞 Support

For issues or questions:
1. Check `.env` configuration
2. Verify broker credentials
3. Check logs in `logs/` directory
4. Ensure market is open

---

**Happy Trading! 📈**
