# FusionTrade Lite

**Streamlined Multi-Broker Options Trading Platform**

A lightweight version of FusionTrade with only essential features for fast, reliable trading.

## ✨ Features

### Core Trading
- **Quick Order** - Fast order placement with symbol, strike, and lot selection
- **Multi-Account Support** - Trade across multiple Upstox/Dhan accounts simultaneously
- **Real-Time Positions** - Live P&L tracking with color-coded display
- **Active Orders** - View and manage all pending/executed orders
- **Stop Loss Management** - Percentage-based SL for all positions
- **Quick Exit** - Exit 25%, 50%, 75%, or 100% of positions instantly

### Removed from Full Version
- ❌ Market analysis and tips buddy
- ❌ Templates system
- ❌ Performance analytics
- ❌ Target management
- ❌ Risk monitoring
- ❌ Advanced charting
- ❌ Closed positions tracking
- ❌ yfinance dependency
- ❌ pandas/numpy dependencies

## 📦 Installation

### Option 1: Run Python Script
```powershell
# Install minimal requirements
pip install -r requirements_lite.txt

# Run the application
python traderchamp_lite.py
```

### Option 2: Build Standalone EXE
```powershell
# Install PyInstaller
pip install pyinstaller

# Build EXE
.\build_lite.ps1

# Run the EXE
.\dist\FusionTradeLite.exe
```

## ⚙️ Configuration

### Update Tokens
The application reads tokens from `config/tokens.json`. Update your access tokens:

```json
{
    "upstox": {
        "broker": "upstox",
        "name": "My Account",
        "access_token": "your_access_token_here"
    },
    "dhan": {
        "broker": "dhan",
        "name": "Dhan Account",
        "access_token": "your_dhan_token_here"
    }
}
```

**Note:** The lite version uses the same token file format as the full version for easy migration.

## 🚀 Usage

### Place Order
1. Select Symbol (NIFTY/BANKNIFTY/SENSEX)
2. Enter Strike Price
3. Choose CALL/PUT
4. Set Lot Quantity
5. Select Order Type (MARKET/LIMIT)
6. Click **PLACE ORDER**

### Apply Stop Loss
1. Enter SL percentage (default: 15%)
2. Click **APPLY SL**
3. SL orders placed for all positions

### Exit Positions
1. Select exit percentage (25/50/75/100%)
2. Click **EXIT**
3. Market orders placed to close positions

## 📊 UI Layout

```
┌─────────────────────────────────────────────────┐
│  [Quick Order Panel]  │  [Positions/Orders]     │
│                       │                         │
│  • Symbol Selection   │  Tab 1: Positions       │
│  • Strike Entry       │  - Symbol, Qty, P&L     │
│  • CE/PE Choice       │                         │
│  • Lot Quantity       │  Tab 2: Active Orders   │
│  • Order Type         │  - Time, Status, etc.   │
│                       │                         │
│  [PLACE ORDER]        │  [Refresh Button]       │
│                       │                         │
│  Stop Loss Controls   │                         │
│  Exit Controls        │                         │
│  [Refresh]            │                         │
└─────────────────────────────────────────────────┘
```

## 💾 File Size Comparison

- **Full Version**: ~50-60 MB (with all dependencies)
- **Lite Version**: ~15-20 MB (minimal dependencies)
- **Startup Time**: 2-3x faster than full version

## 🔧 Technical Details

### Dependencies
- **Python**: 3.8+
- **tkinter**: Built-in GUI framework
- **requests**: HTTP library for API calls
- **PyInstaller**: For building standalone EXE

### Broker Support
- ✅ Upstox
- ✅ Dhan
- ⚠️ Angel One (use full version)
- ⚠️ Zerodha (use full version)

### Supported Operations
- Market orders
- Limit orders
- Stop Loss orders (SL type)
- Multi-account parallel execution
- Real-time position tracking

## 🆚 Lite vs Full Comparison

| Feature | Lite | Full |
|---------|------|------|
| Order Placement | ✅ | ✅ |
| Positions View | ✅ | ✅ |
| Active Orders | ✅ | ✅ |
| Stop Loss | ✅ | ✅ |
| Quick Exit | ✅ | ✅ |
| Multi-Account | ✅ | ✅ |
| Market Analysis | ❌ | ✅ |
| Tips Buddy | ❌ | ✅ |
| Templates | ❌ | ✅ |
| Performance Stats | ❌ | ✅ |
| Risk Monitoring | ❌ | ✅ |
| Closed Positions | ❌ | ✅ |
| File Size | 15-20 MB | 50-60 MB |
| Startup Time | Fast | Moderate |
| Dependencies | Minimal | Heavy |

## 📝 Notes

- The lite version shares the same broker clients with the full version
- Configuration files are compatible between versions
- Logs are written to `logs/` directory (minimal logging)
- No automatic analysis or background tasks
- Focuses on core trading operations only

## 🔄 Migration

To migrate from full version to lite:
1. Copy your `config/tokens.json`
2. Run `traderchamp_lite.py`
3. All trading functions work identically

To return to full version:
1. Run `traderchamp_gui.py`
2. All advanced features available again

## 🐛 Known Limitations

- No instrument search/lookup (manual strike entry)
- No market data updates (positions only)
- Simplified error messages
- No advanced analytics
- No automation features

## 📞 Support

For issues or questions:
- Check `logs/` folder for error messages
- Ensure `config/tokens.json` has valid tokens
- Verify broker credentials are active

---

**FusionTrade Lite** - Trading essentials, nothing more. 🚀
