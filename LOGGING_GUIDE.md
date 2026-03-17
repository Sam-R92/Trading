# FusionTrade Logging System

## Overview
FusionTrade now includes automatic logging with 24-hour rotation to track all trading activities and troubleshoot any issues.

## Features

### ✅ Automatic Log File Creation
- Log files are created in the `logs/` directory
- Filename format: `fusiontrade_YYYYMMDD.log`
- One log file per day

### ✅ 24-Hour Auto-Cleanup
- Old log files (older than 24 hours) are automatically deleted on application startup
- Keeps your logs directory clean and manageable
- Only keeps today's log file

### ✅ What Gets Logged

#### Application Lifecycle
- ✅ Application startup with timestamp
- ✅ Application shutdown with timestamp

#### Order Operations
- ✅ Order placement initiation (symbol, expiry, strike, lots, type)
- ✅ Order validation (missing parameters, invalid limit price)
- ✅ Product type and AMO mode detection
- ✅ Order execution results (success/failure per broker)
- ✅ Detailed error messages with full context

#### Position Management
- ✅ Stop Loss execution (mode, value, results)
- ✅ Increase Qty execution (mode, value, results)
- ✅ Exit Position execution (percent, results)
- ✅ All operations logged with success/failure counts

#### Error Tracking
- ✅ Detailed error messages with stack traces
- ✅ Broker-specific errors (401 expired tokens, 400 validation errors)
- ✅ Order failure reasons with full request details

## Log File Location

```
📁 Traderchamp/
  └── 📁 logs/
      └── 📄 fusiontrade_20251229.log  (today's log)
```

## Viewing Logs

### Method 1: PowerShell Command
```powershell
# View latest log file (last 30 lines)
Get-ChildItem logs/*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | Get-Content -Tail 30

# View entire log file
Get-Content "logs/fusiontrade_20251229.log"

# Follow log in real-time (like tail -f)
Get-Content "logs/fusiontrade_20251229.log" -Wait
```

### Method 2: Text Editor
Simply open the log file in any text editor:
- VS Code: `code logs/fusiontrade_20251229.log`
- Notepad: `notepad logs/fusiontrade_20251229.log`

## Log Entry Format

```
YYYY-MM-DD HH:MM:SS,mmm - LEVEL - MESSAGE
```

**Example:**
```
2025-12-29 18:27:48,522 - INFO - Place Order Initiated: BUY NIFTY 30DEC25 25950 CE Lots:10 Type:MARKET
2025-12-29 18:27:49,957 - ERROR - Order failed for Karthi: 401 Client Error - Token expired
```

## Log Levels

- **INFO**: Normal operations (order placed, positions updated, etc.)
- **WARNING**: Partial success or recoverable issues
- **ERROR**: Failures with detailed context and stack traces

## Sample Log Entries

### Successful Order Placement
```
2025-12-29 18:28:05,231 - INFO - Place Order Initiated: BUY NIFTY 06JAN26 25950 CE Lots:10 Type:MARKET
2025-12-29 18:28:05,231 - INFO - Starting async order placement: Product=INTRADAY
2025-12-29 18:28:05,231 - INFO - AMO Mode: After market hours detected (Time: 18:28:05)
2025-12-29 18:28:05,473 - INFO - Order Execution Results: 2/3 successful
2025-12-29 18:28:05,473 - WARNING - Partial success: 2/3 orders placed
```

### Order Failure (with details)
```
2025-12-29 18:27:49,958 - ERROR - Order failed for Sabari: 400 Client Error: Bad Request
{'errorCode': 'UDAPI1104', 'message': 'Quantity should be multiple of lot size', 
 'invalidValue': 650} | Sent: instrument_token=NSE_FO|65600, qty=650
```

### Position Management
```
2025-12-29 18:28:31,398 - INFO - Stop Loss skipped: No positions
2025-12-29 18:28:38,984 - INFO - Increase Qty skipped: No positions
2025-12-29 18:28:43,786 - INFO - Exit Position skipped: No positions
```

### Application Lifecycle
```
2025-12-29 18:27:37,695 - INFO - ============================================================
2025-12-29 18:27:37,695 - INFO - FusionTrade Application Started
2025-12-29 18:27:37,695 - INFO - Timestamp: 2025-12-29 18:27:37
2025-12-29 18:27:37,695 - INFO - ============================================================
...
2025-12-29 18:29:02,397 - INFO - ============================================================
2025-12-29 18:29:02,397 - INFO - FusionTrade Application Shutting Down
2025-12-29 18:29:02,397 - INFO - Timestamp: 2025-12-29 18:29:02
2025-12-29 18:29:02,397 - INFO - ============================================================
```

## Troubleshooting with Logs

### Common Issues and What to Look For

#### 1. Order Placement Failures
**Search for:** `"Order failed for"`
```powershell
Get-Content logs/*.log | Select-String "Order failed for"
```
Look for error codes:
- `401 Client Error` → Token expired (update .env)
- `400 Bad Request` → Invalid quantity, price, or parameters
- `UDAPI1104` → Quantity not multiple of lot size

#### 2. Token Expiration
**Search for:** `"401"` or `"expired"`
```powershell
Get-Content logs/*.log | Select-String "401|expired"
```

#### 3. AMO Mode Detection
**Search for:** `"AMO Mode"` or `"Regular Mode"`
```powershell
Get-Content logs/*.log | Select-String "AMO Mode|Regular Mode"
```

#### 4. Execution Success Rates
**Search for:** `"Execution Results"`
```powershell
Get-Content logs/*.log | Select-String "Execution Results"
```

## Storage Management

### Automatic Cleanup
- ✅ Runs on every application startup
- ✅ Deletes files older than 24 hours
- ✅ Console notification when files are deleted

### Manual Cleanup (if needed)
```powershell
# View all log files with dates
Get-ChildItem logs/*.log | Select-Object Name, CreationTime, @{N='Size';E={'{0:N2} KB' -f ($_.Length/1KB)}}

# Delete logs older than 7 days (manual)
Get-ChildItem logs/*.log | Where-Object {$_.CreationTime -lt (Get-Date).AddDays(-7)} | Remove-Item
```

## Console Output

Logging also prints to console while the application is running:
```
✅ Logging initialized: C:\Users\sramalingam\Traderchamp\logs\fusiontrade_20251229.log
🗑️ Deleted old log: fusiontrade_20251228.log
Cleaned up 1 old log file(s)
```

## Best Practices

1. **Check logs after errors**: When something goes wrong, check today's log file
2. **Search for specific orders**: Use `Select-String` to find order-related entries
3. **Monitor token expiration**: Look for 401 errors regularly
4. **Track success rates**: Review execution results to ensure all accounts are working
5. **Keep logs during testing**: Don't manually delete logs during the same day

## Technical Details

- **Log rotation**: By date (one file per day)
- **Auto-cleanup**: 24-hour retention
- **Encoding**: UTF-8
- **Format**: Timestamp - Level - Message
- **Location**: `logs/` directory in project root
- **Console output**: Yes (dual logging to file and console)

## Summary

The logging system provides:
- ✅ Complete audit trail of all trading activities
- ✅ Detailed error diagnostics with full context
- ✅ Automatic cleanup to prevent disk space issues
- ✅ Easy troubleshooting with searchable log files
- ✅ Performance tracking (success/failure rates)
- ✅ No manual maintenance required

All logs are stored for 24 hours and then automatically cleaned up, keeping your system lean while providing enough history for debugging recent issues.
