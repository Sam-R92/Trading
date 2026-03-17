# Traderchamp - Multi-Broker Trading Tool

Fast trading tool supporting **up to 5 broker accounts** simultaneously with quick order placement and position management.

## Features

- 🚀 **Quick Order Placement**: Fast options trading (NIFTY/BANKNIFTY/SENSEX/FINNIFTY)
- 📈 **Increase Position**: Add quantity to existing positions
- 🚪 **Exit Orders**: Close positions completely or partially
- 🔄 **Multi-Account Mode**: Trade simultaneously across up to 5 broker accounts
- ⚡ **Fast Interface**: Minimal clicks for order execution
- 📊 **Portfolio Tracking**: Real-time P&L tracking across all accounts
- 💼 **Closed Positions**: View trade history and realized profits

## Supported Brokers

1. **Upstox** ✅ - OAuth2 authentication with token persistence
2. **Dhan** ✅ - Direct access token authentication
3. **Zerodha (Kite Connect)** 🆕 - Daily token generation required
4. **Angel One (SmartAPI)** 🆕 - JWT token authentication
5. **Reserved slot** - For future broker integration

> **Multi-Account Trading**: Execute the same order across all configured accounts simultaneously!

## Quick Start

```powershell
# Setup
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configure accounts
copy .env.example .env
# Edit .env with your credentials

# Run
python traderchamp.py
```

## Configuration

Edit `.env` file (see [MULTI_BROKER_SETUP.md](MULTI_BROKER_SETUP.md) for detailed guide):

```env
# Upstox Account
UPSTOX_API_KEY=your_api_key
UPSTOX_API_SECRET=your_api_secret
UPSTOX_ACCESS_TOKEN=your_access_token
UPSTOX_ACCOUNT_NAME=Sabari

# Dhan Account
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token
DHAN_ACCOUNT_NAME=Karthi

# Zerodha Account (Optional)
ZERODHA_API_KEY=your_api_key
ZERODHA_ACCESS_TOKEN=your_access_token
ZERODHA_ACCOUNT_NAME=Ravi

# Angel One Account (Optional)
ANGELONE_API_KEY=your_api_key
ANGELONE_ACCESS_TOKEN=your_jwt_token
ANGELONE_ACCOUNT_NAME=Priya
```

**Note**: You only need to configure the brokers you want to use. The tool will automatically detect and initialize all configured accounts.

## Usage

1. **Select Broker**: Choose Upstox or Dhan
2. **Quick Order**: Place orders with 7-step quick interface
3. **Manage Positions**: Increase, exit, or partially exit positions
4. **View Portfolio**: Check positions, holdings, funds, and P&L

## Project Structure

```
Traderchamp/
├── traderchamp.py          # Main application
├── brokers/
│   ├── base_broker.py      # Abstract broker interface
│   ├── upstox_client.py    # Upstox implementation
│   └── dhan_client.py      # Dhan implementation
├── config/
│   └── tokens.json         # Token persistence
├── .env                    # Account credentials
└── requirements.txt        # Dependencies
```
# Trading
