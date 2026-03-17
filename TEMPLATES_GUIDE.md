# Strategy Templates Guide

## Overview
Strategy Templates allow you to save and reuse common trading setups, saving time on repetitive configurations.

## Features

### 💾 Save Current Setup
- Saves your current Quick Order configuration as a named template
- Includes: Symbol, Expiry, Strike, Option Type, Lot Size, Order Type, Product Type
- Auto-suggests template name based on current settings (e.g., "NIFTY CE 24000")
- Warns if overwriting an existing template

### 📂 Load Template
- Lists all saved templates in a searchable dialog
- Shows preview of template settings before loading
- Double-click or press Enter to load
- Automatically applies all settings to Quick Order panel
- Smart loading: waits for expiries/strikes to populate before applying

### 🗑️ Delete Template
- Delete one or multiple templates at once
- Hold Ctrl to select multiple templates
- Confirms before deletion
- Shows template details (Symbol, Type, Strike) for easy identification

## How to Use

### Saving a Template
1. Configure your desired settings in the Quick Order panel:
   - Select Symbol (e.g., NIFTY)
   - Choose Expiry date
   - Select Strike price
   - Choose Option Type (CE/PE)
   - Set Lot Size
   - Select Order Type (MARKET/LIMIT)
   - Choose Product Type (MIS/NRML)

2. Go to **Templates → Save Current Setup**

3. Enter a descriptive name (or use the suggested name)
   - Example: "NIFTY 24000 CE Weekly"
   - Example: "BANKNIFTY 50000 PE Monthly"

4. Click **Save**

### Loading a Template
1. Go to **Templates → Load Template**

2. Select a template from the list
   - Preview shows all settings
   - Templates are sorted alphabetically

3. Double-click or press Enter to load
   - All Quick Order settings will be updated automatically
   - You can then modify specific fields if needed

### Deleting Templates
1. Go to **Templates → Delete Template**

2. Select one or more templates:
   - Single click to select one
   - Hold Ctrl and click to select multiple

3. Click **Delete** and confirm

## Use Cases

### 1. Weekly Options Strategy
Save templates for common weekly strikes:
```
Templates:
- "NIFTY Weekly +500 CE"  → Current ATM + 500
- "NIFTY Weekly -500 PE"  → Current ATM - 500
- "BANKNIFTY Weekly ATM"  → Current ATM straddle
```

### 2. Hedging Strategies
Save your hedge configurations:
```
Templates:
- "NIFTY Protective Put"   → ITM PE for hedging
- "BANKNIFTY Iron Condor"  → 4-leg spread setup
- "SENSEX Collar"          → Long stock + Put + Call
```

### 3. Quick Scalping Setups
Save your favorite scalping instruments:
```
Templates:
- "NIFTY ATM CE 1 Lot"     → Fast entry for ATM calls
- "BANKNIFTY OTM PE 2 Lot" → Quick OTM put scalp
```

### 4. Time-Based Strategies
Save different settings for different times:
```
Templates:
- "Morning Gap Fill"       → High lot, MIS, Market order
- "Afternoon Swing"        → Medium lot, NRML, Limit order
- "EOD Overnight"          → Low lot, NRML, Limit order
```

## Storage Location
Templates are stored in: `config/templates.json`

Example structure:
```json
{
  "NIFTY 24000 CE Weekly": {
    "symbol": "NIFTY",
    "expiry": "2025-01-02",
    "strike": "24000",
    "option_type": "CE",
    "lot_size": 1,
    "order_type": "MARKET",
    "product_type": "MIS"
  },
  "BANKNIFTY 50000 PE": {
    "symbol": "BANKNIFTY",
    "expiry": "2025-01-08",
    "strike": "50000",
    "option_type": "PE",
    "lot_size": 2,
    "order_type": "LIMIT",
    "product_type": "NRML"
  }
}
```

## Keyboard Shortcuts
- **Save dialog**: Enter to save, Escape to cancel
- **Load dialog**: Enter or Double-click to load, Escape to cancel
- **Delete dialog**: Escape to cancel

## Tips

### Best Practices
1. **Use descriptive names**: Include symbol, strike, and strategy type
2. **Organize by strategy**: Group templates by trading strategy
3. **Regular cleanup**: Delete unused templates monthly
4. **Backup templates**: Copy `config/templates.json` for backup

### Naming Conventions
Good template names:
- ✅ "NIFTY 24000 CE Iron Condor Long"
- ✅ "BANKNIFTY Weekly Straddle"
- ✅ "SENSEX Monthly Hedge Put"

Avoid:
- ❌ "Template1", "Test", "My Strategy"
- ❌ Too long names that are hard to scan

### Common Workflows

**Daily Trader:**
```
1. Save 3-4 favorite strikes as templates at week start
2. Load template each morning
3. Adjust lot size based on volatility
4. Delete expired templates on Friday
```

**Swing Trader:**
```
1. Save monthly expiry setups
2. Load template and adjust strike based on market
3. Use NRML product type
4. Keep templates for entire month
```

**Scalper:**
```
1. Save ATM templates for NIFTY/BANKNIFTY
2. Quick load during volatile moves
3. Always MIS, always MARKET
4. Update templates weekly
```

## Troubleshooting

### Template Not Loading Properly
- Check if expiry is still available (may have expired)
- Ensure symbol data is loaded (wait for UI to populate)
- Try loading again after 2-3 seconds

### Template File Corrupted
- Delete `config/templates.json`
- Restart application (will create fresh file)
- Re-save your templates

### Lost Templates After Update
- Check `config/templates.json` exists
- If missing, templates were deleted
- Always backup before major updates

## Advanced: Manual Editing

You can manually edit `config/templates.json` to:
- Bulk create templates from Excel/CSV data
- Share templates with other traders
- Backup/restore across machines

Just ensure valid JSON format after editing!

## Future Enhancements (Planned)
- Import/Export templates to CSV
- Share templates with other users
- Template categories/folders
- Auto-update templates on expiry rollover
- Template keyboard shortcuts (F1-F12)
