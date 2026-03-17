# TraderChamp GUI - Troubleshooting Guide

## ✅ GUI is Running Successfully

The GUI should now be displaying with:
- Loading screen during initialization
- Instrument data loaded (Upstox: 18,173 options, Dhan: 10,957 options)
- Multi-account mode enabled (if both tokens are valid)

## 🔧 Common Issues & Solutions

### 1. GUI Opens but No Data Appears

**Symptoms:**
- Window opens but positions table is empty
- Expiry dropdown shows no data
- No error messages

**Solutions:**

#### Check Token Status
Your tokens expire daily. Check `.env` file:
```
UPSTOX_ACCESS_TOKEN=eyJ0eXAi... (expires daily)
DHAN_ACCESS_TOKEN=eyJ0eXAi... (expires daily)
```

#### Regenerate Tokens
```powershell
# Close GUI first
python traderchamp.py
# Type: token
# Select broker (1 for Upstox, 2 for Dhan)
# Follow login flow
```

### 2. 401 Unauthorized Error

**Symptoms:**
- Error message: "401 Client Error: Unauthorized"
- Console shows: "Token expired"

**Solution:**
```powershell
# 1. Close GUI
# 2. Run console app
python traderchamp.py

# 3. Generate new token
# Type: token
# Select: 1 (Upstox) or 2 (Dhan)
# Login in browser
# Copy redirect URL
# Paste in console

# 4. Restart GUI
python traderchamp_gui.py
```

### 3. GUI Won't Start

**Symptoms:**
- Black window appears then closes
- Error before loading screen

**Check:**
```powershell
# Run with error output
python traderchamp_gui.py 2>&1

# Common issues:
# - Missing .env file
# - Invalid token format
# - Network connectivity
```

### 4. No Positions Showing

**Possible Causes:**

1. **No active positions**: Check with console app
   ```powershell
   python traderchamp.py
   # Select option 6 (View Positions)
   ```

2. **Token expired**: See solution #2 above

3. **Network issue**: Check internet connection

### 5. Buttons Not Working

**Symptoms:**
- Clicking buttons does nothing
- No error messages

**Solutions:**
- Check console output for errors (terminal window)
- Ensure positions exist before using action buttons
- Restart GUI

## 📊 Verifying GUI is Working

### Loading Screen Sequence:
1. "Loading..." (appears immediately)
2. "Initializing trader..." (1-2 seconds)
3. "Downloading instrument data..." (2-5 seconds if downloading)
4. "Connecting to brokers..." (1-2 seconds)
5. Main UI appears with positions table

### Console Output (Normal):
```
🔄 Checking instrument masters...
  ✅ Upstox instruments up to date
  ✅ Dhan instruments up to date
  📖 Loading Upstox instruments...
  ✅ Loaded 18173 Upstox options
  📖 Loading Dhan instruments...
  ✅ Loaded 10957 Dhan options
✅ Multi-account mode enabled: 2 accounts
```

### Signs GUI is Working:
✅ Loading screen appears and disappears
✅ Main window with positions table visible
✅ Expiry dropdown populated with dates
✅ Action buttons clickable (may show "No positions" if empty)
✅ Console shows instrument loading messages

## 🚨 Error Messages Decoded

### "No broker accounts configured!"
**Fix:** Check `.env` file has both:
- UPSTOX_API_KEY and UPSTOX_ACCESS_TOKEN
- DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN

### "Failed to setup accounts: ..."
**Fix:** 
- Verify token format (no extra spaces)
- Regenerate expired tokens
- Check credentials are correct

### "Error loading expiries"
**Fix:**
- Instrument masters not loaded
- Close and restart GUI
- Check internet connection

### "Token expired. Please regenerate access token."
**Fix:** See solution #2 above

## 🔄 Daily Workflow

### Morning (Before Market):
```powershell
# 1. Regenerate tokens (both brokers)
python traderchamp.py
# Type: token → Select 1 (Upstox) → Login → Paste URL
# Type: token → Select 2 (Dhan) → Login → Paste URL

# 2. Start GUI
python traderchamp_gui.py
```

### During Trading:
- GUI auto-refreshes positions every 5 seconds
- Use action buttons for position management
- Monitor console window for errors

### After Market:
- Close GUI normally (X button)
- Review closed positions in console app if needed

## 📝 Debug Mode

To see detailed error messages:

```powershell
# Run with full output
python traderchamp_gui.py 2>&1 | Tee-Object -FilePath gui_debug.log

# Check log file for errors
cat gui_debug.log
```

## ⚙️ Performance Tips

1. **Slow Loading**: 
   - Normal on first run (downloads instrument data)
   - Subsequent runs use cached data (faster)

2. **High CPU Usage**:
   - Normal during auto-refresh (every 5 seconds)
   - Positions table updates create brief CPU spikes

3. **Memory Usage**:
   - ~100-150MB typical
   - ~200MB if many positions/orders

## 🆘 Still Not Working?

1. **Delete instrument cache**:
   ```powershell
   Remove-Item data/*.csv
   # Restart GUI to re-download
   ```

2. **Reset environment**:
   ```powershell
   # Backup .env
   Copy-Item .env .env.backup
   
   # Regenerate all tokens
   python traderchamp.py
   ```

3. **Check Python version**:
   ```powershell
   python --version
   # Should be 3.8 or higher
   ```

4. **Verify dependencies**:
   ```powershell
   pip list | Select-String "requests|python-dotenv"
   ```

## 📞 Quick Reference

| Issue | Quick Fix |
|-------|-----------|
| No data showing | Regenerate tokens |
| 401 error | Token expired - regenerate |
| GUI won't start | Check .env file exists |
| Empty positions | Check with console app |
| Buttons not working | Restart GUI |
| Slow loading | Normal first run |

## ✅ Current Status

Based on your latest run:
- ✅ GUI initializing successfully
- ✅ Instrument masters loaded
- ✅ Ready to display positions (if any exist)
- ⚠️  If no positions showing, tokens may be expired

**Next Step**: Check if you have active positions by running console app, or regenerate tokens if you see 401 errors.
