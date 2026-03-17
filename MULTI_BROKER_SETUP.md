# Traderchamp Multi-Broker Setup Guide

## Supported Brokers (Up to 5 accounts)

Traderchamp now supports up to 5 broker accounts running simultaneously:

1. **Upstox** ✅ (Configured)
2. **Dhan** ✅ (Configured)
3. **Zerodha (Kite Connect)** 🆕 (Ready to configure)
4. **Angel One (SmartAPI)** 🆕 (Ready to configure)
5. **Reserved slot** (For future broker integration)

---

## Quick Start

### Step 1: Install Required Dependencies

```bash
pip install kiteconnect smartapi-python
```

### Step 2: Configure Broker Credentials

Add your broker credentials to `.env` file:

#### For Zerodha:
```env
ZERODHA_API_KEY=your_api_key
ZERODHA_API_SECRET=your_api_secret
ZERODHA_ACCESS_TOKEN=your_access_token
ZERODHA_ACCOUNT_NAME=Your Name
```

**Getting Zerodha Credentials:**
1. Visit https://kite.trade/
2. Sign up for Kite Connect API
3. Create an app to get API Key and Secret
4. Generate access token using the login flow

#### For Angel One:
```env
ANGELONE_API_KEY=your_api_key
ANGELONE_API_SECRET=your_client_secret
ANGELONE_ACCESS_TOKEN=your_jwt_token
ANGELONE_ACCOUNT_NAME=Your Name
```

**Getting Angel One Credentials:**
1. Visit https://smartapi.angelbroking.com/
2. Register for SmartAPI
3. Get your API Key from the dashboard
4. Generate JWT token using client code and password

---

## Configuration Examples

### Example 1: All 4 Brokers Active
```env
# Upstox
UPSTOX_API_KEY=abc123
UPSTOX_ACCESS_TOKEN=xyz789
UPSTOX_ACCOUNT_NAME=Sabari

# Dhan
DHAN_CLIENT_ID=1100123456
DHAN_ACCESS_TOKEN=token123
DHAN_ACCOUNT_NAME=Karthi

# Zerodha
ZERODHA_API_KEY=kite123
ZERODHA_ACCESS_TOKEN=token456
ZERODHA_ACCOUNT_NAME=Ravi

# Angel One
ANGELONE_API_KEY=angel123
ANGELONE_ACCESS_TOKEN=jwt789
ANGELONE_ACCOUNT_NAME=Priya
```

### Example 2: Only Upstox and Zerodha
```env
# Upstox
UPSTOX_API_KEY=abc123
UPSTOX_ACCESS_TOKEN=xyz789
UPSTOX_ACCOUNT_NAME=Account 1

# Zerodha
ZERODHA_API_KEY=kite123
ZERODHA_ACCESS_TOKEN=token456
ZERODHA_ACCOUNT_NAME=Account 2
```

---

## Broker-Specific Features

| Feature | Upstox | Dhan | Zerodha | Angel One |
|---------|--------|------|---------|-----------|
| F&O Trading | ✅ | ✅ | ✅ | ✅ |
| Market Orders | ✅ | ✅ | ✅ | ✅ |
| Limit Orders | ✅ | ✅ | ✅ | ✅ |
| Stop Loss | ✅ | ✅ | ✅ | ✅ |
| Position Tracking | ✅ | ✅ | ✅ | ✅ |
| Portfolio View | ✅ | ✅ | ✅ | ✅ |
| Multi-Account | ✅ | ✅ | ✅ | ✅ |

---

## Order Type Mapping

### Product Types
- **MIS/INTRADAY**: Square off before market close (auto-square off by broker)
- **NRML/CARRYFORWARD**: Carry forward overnight

### Broker-Specific Mapping
| Common | Upstox | Dhan | Zerodha | Angel One |
|--------|--------|------|---------|-----------|
| INTRADAY | I | INTRADAY | MIS | INTRADAY |
| CARRYFORWARD | D | MARGIN | NRML | CARRYFORWARD |

---

## API Rate Limits

| Broker | Orders/Second | Positions/Minute |
|--------|---------------|------------------|
| Upstox | 10 | 60 |
| Dhan | 10 | 60 |
| Zerodha | 10 | 60 |
| Angel One | 5 | 30 |

**Note:** Traderchamp automatically handles parallel execution across all active brokers.

---

## Troubleshooting

### Common Issues

#### 1. "Token expired" error
- Regenerate access token from broker dashboard
- Update token in `.env` file
- Restart the application

#### 2. "Instrument not found"
- Ensure instrument masters are up to date
- Check symbol format matches broker requirements

#### 3. "Insufficient funds"
- Check available margin in Portfolio tab
- Reduce lot size or number of contracts

#### 4. Zerodha specific: "Invalid access token"
- Zerodha tokens expire daily at midnight
- Use Kite Connect login flow to generate new token each day

#### 5. Angel One specific: "JWT token expired"
- Angel One tokens expire after a certain period
- Regenerate JWT token using SmartAPI session

---

## Security Best Practices

1. **Never commit `.env` file** to version control
2. **Rotate tokens regularly** (at least monthly)
3. **Use read-only tokens** where possible
4. **Monitor API usage** to avoid rate limit penalties
5. **Enable 2FA** on all broker accounts

---

## Advanced: Adding More Brokers

To add a 5th broker (e.g., Fyers, ICICI Direct):

1. Create `brokers/newbroker_client.py` extending `BaseBroker`
2. Update `brokers/__init__.py` to export the new client
3. Add initialization code in `traderchamp.py` `_init_multi_account()`
4. Add credentials to `.env` file

---

## Support

For broker-specific API documentation:
- **Upstox**: https://upstox.com/developer/api-documentation
- **Dhan**: https://dhanhq.co/docs/
- **Zerodha**: https://kite.trade/docs/
- **Angel One**: https://smartapi.angelbroking.com/docs

For Traderchamp issues, check the logs in `logs/` directory.
