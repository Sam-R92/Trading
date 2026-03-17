# 📊 Max Lot Calculator Feature

## Overview
The Max Lot Calculator automatically displays the maximum affordable lot count for major indices (NIFTY, BANKNIFTY, SENSEX) based on your **total available margin**.

## Location
The calculator is displayed in the **Order Entry Panel** (left side), right below the "Total Available" margin display:

```
Total Available: ₹9,62,682.13
📊 Max Lots: NI:98 | BA:106 | SE:120
```

## How It Works

### Calculation Formula
```
Max Lots = MIN(Affordable Lots, Exchange Max Lots)

Where:
- Affordable Lots = Available Margin ÷ (Avg Premium × Lot Size)
- Exchange Max Lots = Maximum allowed before freeze limit
```

### Index Parameters

| Index | Lot Size | Max Lots | Freeze Qty | Avg Premium Used |
|-------|----------|----------|------------|------------------|
| NIFTY | 65 | 13 | 845 | ₹150 |
| BANKNIFTY | 30 | 30 | 900 | ₹300 |
| SENSEX | 20 | 45 | 900 | ₹400 |

### Example Calculation

**Available Margin**: ₹9,62,682.13

**NIFTY (NI)**:
- Margin per lot = ₹150 × 65 = ₹9,750
- Affordable lots = ₹962,682 ÷ ₹9,750 = 98 lots
- Exchange max = 13 lots
- **Result: 13 lots** (capped at exchange limit)

**BANKNIFTY (BA)**:
- Margin per lot = ₹300 × 30 = ₹9,000
- Affordable lots = ₹962,682 ÷ ₹9,000 = 106 lots
- Exchange max = 30 lots
- **Result: 30 lots** (capped at exchange limit)

**SENSEX (SE)**:
- Margin per lot = ₹400 × 20 = ₹8,000
- Affordable lots = ₹962,682 ÷ ₹8,000 = 120 lots
- Exchange max = 45 lots
- **Result: 45 lots** (capped at exchange limit)

## Display Format

The calculator shows abbreviated results:
- **NI** = NIFTY (first 2 letters)
- **BA** = BANKNIFTY
- **SE** = SENSEX

**Full Display**: `📊 Max Lots: NI:13 | BA:30 | SE:45`

## Auto-Update
The max lot calculator automatically updates:
- ✅ Every **30 seconds** (along with margin refresh)
- ✅ When application starts
- ✅ After placing orders (when margin changes)

## Important Notes

### 1. Conservative Premium Estimates
The calculator uses **conservative average premiums** for ATM (At-The-Money) options:
- NIFTY: ₹150 (actual premiums typically ₹80-200)
- BANKNIFTY: ₹300 (actual premiums typically ₹200-400)
- SENSEX: ₹400 (actual premiums typically ₹300-500)

This ensures you don't over-leverage based on the calculator.

### 2. Exchange Freeze Limits
The calculator respects exchange freeze limits:
- NIFTY: Max 13 lots (845 qty)
- BANKNIFTY: Max 30 lots (900 qty)
- SENSEX: Max 45 lots (900 qty)

Orders exceeding these limits will be rejected by the exchange.

### 3. Real Premium Varies
Actual option premiums depend on:
- **Strike distance** from spot price (ITM/ATM/OTM)
- **Volatility** (VIX levels)
- **Time to expiry** (theta decay)
- **Market conditions**

Always verify actual premium before placing large orders.

### 4. Margin Buffer
Consider keeping a **margin buffer** (10-20%) for:
- MTM (Mark-to-Market) losses
- Multiple positions
- Unexpected volatility

## Use Cases

### 1. Quick Position Sizing
See at a glance how many lots you can afford for each index without manual calculation.

### 2. Multi-Index Strategy
Compare affordability across indices:
```
📊 Max Lots: NI:13 | BA:30 | SE:45
```
- SENSEX allows more lots (cheaper per lot)
- NIFTY has highest per-lot cost

### 3. Capital Allocation
Plan your trades based on available capital:
- High margin? Trade multiple indices
- Low margin? Focus on one index

### 4. Risk Management
Avoid over-leveraging by seeing realistic lot counts based on current margin.

## Troubleshooting

### "Calculating..."
- Margin data not yet loaded
- Wait 2-3 seconds after app starts

### "Load margin first"
- No margin data available
- Click refresh or restart application

### "Insufficient margin"
- Available margin < ₹8,000
- Cannot afford even 1 lot of any index

### "Error calculating"
- Internal calculation error
- Check console for error message

## Technical Details

### Function Location
- **File**: `traderchamp_gui.py`
- **Function**: `calculate_max_lots()` (lines ~2053-2096)
- **UI Element**: `self.max_lot_var` and `self.max_lot_label`

### Update Trigger
```python
# Called after margin refresh
self.root.after(0, self.calculate_max_lots)
```

### Premium Assumptions
```python
indices = {
    "NIFTY": {"lot_size": 65, "max_lots": 13, "avg_premium": 150},
    "BANKNIFTY": {"lot_size": 30, "max_lots": 30, "avg_premium": 300},
    "SENSEX": {"lot_size": 20, "max_lots": 45, "avg_premium": 400}
}
```

## Example Scenarios

### Scenario 1: High Margin (₹10,00,000)
```
📊 Max Lots: NI:13 | BA:30 | SE:45
```
All indices capped at exchange limits - you have sufficient capital.

### Scenario 2: Medium Margin (₹2,00,000)
```
📊 Max Lots: NI:13 | BA:22 | SE:25
```
- NIFTY: Full capacity (13 lots)
- BANKNIFTY: 22 lots (below max 30)
- SENSEX: 25 lots (below max 45)

### Scenario 3: Low Margin (₹50,000)
```
📊 Max Lots: NI:5 | BA:5 | SE:6
```
Limited capacity across all indices - trade carefully.

### Scenario 4: Very Low Margin (₹5,000)
```
📊 Max Lots: Insufficient margin
```
Cannot afford any index - add funds or wait for positions to close.

## Best Practices

1. **Don't Max Out**: Use only 50-70% of calculated max lots to maintain margin buffer
2. **Verify Premium**: Check actual option premium before placing large orders
3. **Consider MTM**: Keep buffer for mark-to-market movements
4. **Multiple Positions**: Divide available lots across different strikes/expiries
5. **Risk Management**: Never risk entire capital on single trade

## Summary

The Max Lot Calculator provides:
- ✅ **Real-time** affordable lot counts
- ✅ **Exchange-compliant** (respects freeze limits)
- ✅ **Conservative** premium estimates
- ✅ **Auto-updating** every 30 seconds
- ✅ **Easy to read** abbreviated format

Use it as a **quick reference** for position sizing, not absolute trading limits. Always verify actual premiums and maintain margin buffers for safe trading.
