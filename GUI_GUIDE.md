# TraderChamp GUI - Quick Start Guide

## 🚀 Launch GUI

### Windows:
```
Double-click: run_gui.bat
```

### Command Line:
```powershell
python traderchamp_gui.py
```

## 📊 GUI Layout

### Left Panel - Order Entry
- **Symbol Selection**: NIFTY, BANKNIFTY, SENSEX, FINNIFTY, MIDCPNIFTY
- **Expiry**: Select from dropdown (shows 5 upcoming expiries)
- **Strike Price**: Enter and click "Load"
- **CALL/PUT**: Radio buttons (Green = CALL, Red = PUT)
- **Lot Quantity**: Use +/- buttons to adjust
- **Order Type**: MARKET or LIMIT
- **BUY/SELL**: Large buttons to place orders

### Right Panel - Positions & Actions

#### Positions Table (Auto-refresh every 5 seconds)
- Broker | Symbol | Qty | Entry | LTP | P&L | Time
- Color-coded: Green = Profit, Red = Loss

#### Action Buttons

**Row 1:**
- 🛡️ **STOP LOSS** (Orange) - Set SL % for all positions
- 📈 **INCREASE** (Blue) - Add to all positions (25%, 50%, 75%, 100%, custom)

**Row 2:**
- 🚪 **EXIT** (Red) - Close all positions
- 📊 **PARTIAL EXIT** (Orange) - Exit partial quantity (25%, 50%, 75%, custom)

**Row 3:**
- 💼 **PORTFOLIO** (Purple) - View account summary
- 🔄 **REFRESH** (Green) - Manual refresh

## 🛡️ Stop Loss Configuration

1. Click "STOP LOSS" button
2. Adjust percentage using:
   - `--` = Decrease 1%
   - `-` = Decrease 0.5%
   - Type exact % in box
   - `+` = Increase 0.5%
   - `++` = Increase 1%
3. Preview shows SL price and potential loss for each position
4. Click "PLACE SL ORDERS" to execute (all accounts simultaneously)

## 📈 Increase Position

1. Click "INCREASE" button
2. Select percentage:
   - 25%, 50%, 75%, 100% quick buttons
   - Or enter custom percentage
3. Confirmation shows calculation for each account
4. Orders placed in parallel across all accounts

## 🚪 Exit & Partial Exit

### Full Exit:
- Click "EXIT" → Confirm → All positions closed

### Partial Exit:
- Click "PARTIAL EXIT"
- Choose: 25%, 50%, 75%, or custom %
- Applies to ALL positions across ALL accounts

## 💼 Portfolio View

Shows combined summary:
- Available margin per account
- Used margin per account
- P&L per account
- Combined totals and ROI

## ⚡ Key Features

✅ **Multi-Account Parallel Trading** - Orders placed simultaneously
✅ **Auto-Refresh** - Positions update every 5 seconds
✅ **Color-Coded UI** - Dark theme with clear profit/loss indicators
✅ **Non-Blocking UI** - All operations run in background threads
✅ **Percentage-Based Actions** - Intuitive % controls for all position management
✅ **Real-Time Preview** - See calculations before placing orders

## 🔧 Configuration

Access tokens configured in `.env` file:
```
UPSTOX_API_KEY=...
UPSTOX_ACCESS_TOKEN=...
UPSTOX_ACCOUNT_NAME=Sabari

DHAN_CLIENT_ID=...
DHAN_ACCESS_TOKEN=...
DHAN_ACCOUNT_NAME=Karthi
```

**Note:** Tokens expire daily. Regenerate using console app (`python traderchamp.py` → type `token`)

## 🎨 Design Reference

Based on provided handwritten design:
- Left panel: Order entry form
- Right panel: Positions table + 6 action buttons (2x3 grid)
- Dark theme: Black background, green accents
- Color coding: Green (profit/buy), Red (loss/sell), Orange (warning), Blue (info)

## 💡 Tips

1. **Before Market Open**: Regenerate access tokens
2. **During Trading**: Let auto-refresh handle position updates
3. **Stop Loss**: Set immediately after entry
4. **Exit Strategy**: Use partial exit for profit booking
5. **Increase Position**: Use % options for consistent scaling

## ⚠️ Important

- All actions apply to **ALL accounts** simultaneously
- Confirm dialogs show exact details before execution
- Parallel execution ensures sub-100ms timing difference between brokers
- Auto-refresh can be paused by closing/reopening app
