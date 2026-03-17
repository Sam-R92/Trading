# Invalid Token Handling

## Overview
FusionTrade now automatically detects and disables broker accounts with expired or invalid tokens, preventing continuous error messages during order execution.

## How It Works

### 🔍 Token Validation on Startup
When the application starts, each Dhan account is validated:

1. **Test API Call**: Attempts to fetch positions using `get_positions()`
2. **Token Check**: If the response indicates:
   - ✅ **Valid token** → Account enabled for trading
   - ❌ **401 error** → Account disabled automatically
   - ❌ **"expired" or "invalid"** in error → Account disabled

### 🚫 Automatic Account Disabling

When an invalid token is detected:
```
⚠️  Dhan token expired/invalid for Karthi - account disabled
2025-12-29 18:32:48 - ERROR - Dhan account Karthi: Token expired or invalid
```

The account is added to the `invalid_brokers` set and **completely skipped** for all operations.

### 📊 Order Execution Filtering

**Before (with invalid token):**
```
Order Execution Results: 2/3 successful
ERROR - Order failed for Karthi: 401 Client Error (repeated every order)
```

**After (invalid token filtered):**
```
Order Execution Results: 2/2 successful
INFO - All orders executed successfully
```

Invalid accounts are silently skipped - **no error messages** during order placement!

## When Tokens Are Validated

### 1. Application Startup (Primary)
- Dhan accounts validated during `setup_multi_account()`
- Test call to `get_positions()` endpoint
- Invalid accounts disabled before GUI loads

### 2. Position Fetch (Secondary)
- During `refresh_positions()` calls
- If 401 error detected → account marked invalid
- Subsequent operations skip this account

### 3. Margin Fetch (Secondary)
- During margin refresh
- If 401 error detected → account marked invalid
- Margin display skips this account

## Benefits

### ✅ No More Error Spam
**Before:**
```
⚠️  Error fetching from Karthi: 401 Client Error
⚠️  Error fetching from Karthi: 401 Client Error (repeats 20+ times)
ERROR - Order failed for Karthi: 401 Client Error
```

**After:**
```
⚠️  Dhan token expired/invalid for Karthi - account disabled
(No further errors - account silently skipped)
```

### ✅ Accurate Success Reporting
- Success rate shows **2/2** instead of **2/3** (excluding invalid account)
- "All orders executed successfully" message shown
- No partial success warnings for unavoidable failures

### ✅ Clean Logs
**Log entries now show:**
```
2025-12-29 18:32:48 - ERROR - Dhan account Karthi: Token expired or invalid
2025-12-29 18:33:11 - INFO - Order Execution Results: 2/2 successful
2025-12-29 18:33:11 - INFO - All orders executed successfully
```

**Instead of repeated errors:**
```
2025-12-29 18:28:05 - ERROR - Order failed for Karthi: 401 Client Error
2025-12-29 18:28:15 - ERROR - Order failed for Karthi: 401 Client Error
2025-12-29 18:28:25 - ERROR - Order failed for Karthi: 401 Client Error
(continues indefinitely...)
```

### ✅ Automatic Recovery
- When you update the token in `.env`
- Restart the application
- Account automatically re-validated and enabled if token is valid

## Technical Implementation

### Invalid Broker Tracking
```python
# Set initialized at GUI startup
self.invalid_brokers = set()  # {'dhan', 'dhan2', etc.}

# Token validation during setup
if '401' in error or 'expired' in error or 'invalid' in error:
    self.invalid_brokers.add('dhan')
    logging.error(f"Dhan account {name}: Token expired or invalid")
```

### Order Execution Filtering
```python
# Filter out invalid brokers before order placement
valid_brokers = {k: v for k, v in active_brokers.items() 
                if k not in self.invalid_brokers}

# Only execute orders to valid accounts
for key, info in valid_brokers.items():
    place_order(key, info)
```

### Position/Margin Fetch Marking
```python
# During fetch operations, if 401 detected:
if '401' in str(error):
    self.invalid_brokers.add(broker_key)
    logging.warning(f"Broker {name} marked as invalid")
```

## What Gets Skipped

When an account is marked invalid, it's automatically excluded from:

1. ✅ **Order Placement** - No order attempts to invalid accounts
2. ✅ **Position Fetch** - Skipped during refresh (no error spam)
3. ✅ **Margin Calculation** - Excluded from total margin
4. ✅ **Stop Loss Application** - Only applied to valid accounts
5. ✅ **Increase Qty** - Only executed on valid accounts
6. ✅ **Exit Position** - Only executed on valid accounts

## Console Output Examples

### Startup Detection
```
✅ Upstox account setup: Sabari
⚠️  Dhan token expired/invalid for Karthi - account disabled
✅ Upstox account 2 setup: Karthi1
✅ Multi-account mode enabled: 2 accounts
```

### Order Execution
```
🌙 After Market Hours - Placing AMO orders (product=I)
🔑 Sabari: instrument_key = NSE_FO|58799
🔑 Karthi1: instrument_key = NSE_FO|58799
(Karthi skipped - no attempt made)
```

### Success Message
```
✅ Order executed! (2/2 accounts)
Positions updating...
```

## Fixing Invalid Tokens

### Step 1: Generate New Token
- Go to your Dhan account portal
- Generate a new access token
- Copy the token

### Step 2: Update .env File
```env
DHAN_ACCESS_TOKEN=your_new_token_here
```

### Step 3: Restart Application
```powershell
python traderchamp_gui.py
```

### Step 4: Verify
Look for:
```
✅ Dhan account setup: Karthi
✅ Multi-account mode enabled: 3 accounts
```

## Logging

All token validation events are logged:

### Successful Validation
```
(No log entry - silent success)
```

### Failed Validation
```
2025-12-29 18:32:48 - ERROR - Dhan account Karthi: Token expired or invalid - 401 Client Error
2025-12-29 18:32:48 - WARNING - Broker Karthi (dhan) marked as invalid due to 401 error
```

### Order Execution Skip
```
2025-12-29 18:33:11 - WARNING - Skipping brokers with invalid tokens: Karthi
2025-12-29 18:33:11 - INFO - Order Execution Results: 2/2 successful
```

## Summary

✅ **Automatic Detection**: Invalid tokens detected on startup
✅ **Smart Filtering**: Invalid accounts skipped automatically
✅ **No Error Spam**: Clean console and log output
✅ **Accurate Reporting**: Success rates exclude unavailable accounts
✅ **Easy Recovery**: Simply update token and restart
✅ **Zero Configuration**: Works automatically with no user action needed

The system now handles expired tokens gracefully, allowing you to continue trading with valid accounts while being notified once about the invalid account.
