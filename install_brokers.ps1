# Traderchamp - Install Broker Dependencies
# Run this script to install required dependencies for additional brokers

Write-Host "================================" -ForegroundColor Cyan
Write-Host "Traderchamp Broker Dependencies" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment is activated
if (-not $env:VIRTUAL_ENV) {
    Write-Host "⚠️  Virtual environment not activated!" -ForegroundColor Yellow
    Write-Host "Run: .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host ""
    $response = Read-Host "Continue anyway? (y/n)"
    if ($response -ne "y") {
        exit
    }
}

Write-Host "Current Setup:" -ForegroundColor Green
Write-Host "✅ Upstox - Already supported" -ForegroundColor Gray
Write-Host "✅ Dhan - Already supported" -ForegroundColor Gray
Write-Host ""

# Ask which brokers to install
Write-Host "Which brokers do you want to add?" -ForegroundColor Cyan
Write-Host "[1] Zerodha (Kite Connect)" -ForegroundColor White
Write-Host "[2] Angel One (SmartAPI)" -ForegroundColor White
Write-Host "[3] Both Zerodha and Angel One" -ForegroundColor White
Write-Host "[4] None (Skip installation)" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Enter choice (1-4)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "Installing Zerodha (Kite Connect)..." -ForegroundColor Yellow
        pip install kiteconnect
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Zerodha support installed successfully!" -ForegroundColor Green
        } else {
            Write-Host "❌ Failed to install Zerodha support" -ForegroundColor Red
        }
    }
    "2" {
        Write-Host ""
        Write-Host "Installing Angel One (SmartAPI)..." -ForegroundColor Yellow
        pip install smartapi-python
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Angel One support installed successfully!" -ForegroundColor Green
        } else {
            Write-Host "❌ Failed to install Angel One support" -ForegroundColor Red
        }
    }
    "3" {
        Write-Host ""
        Write-Host "Installing both Zerodha and Angel One..." -ForegroundColor Yellow
        pip install kiteconnect smartapi-python
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Both brokers installed successfully!" -ForegroundColor Green
        } else {
            Write-Host "❌ Failed to install one or more brokers" -ForegroundColor Red
        }
    }
    "4" {
        Write-Host ""
        Write-Host "Skipping installation." -ForegroundColor Gray
    }
    default {
        Write-Host ""
        Write-Host "Invalid choice. Exiting." -ForegroundColor Red
        exit
    }
}

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Add broker credentials to .env file" -ForegroundColor White
Write-Host "   See MULTI_BROKER_SETUP.md for details" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Get API credentials:" -ForegroundColor White
Write-Host "   Zerodha: https://kite.trade/" -ForegroundColor Gray
Write-Host "   Angel One: https://smartapi.angelbroking.com/" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Run the application:" -ForegroundColor White
Write-Host "   python traderchamp_gui.py" -ForegroundColor Gray
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
