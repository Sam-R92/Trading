# Traderchamp Setup Script
# Copies your existing .env file and creates necessary directories

Write-Host "🚀 Setting up Traderchamp..." -ForegroundColor Cyan

# Create necessary directories
$directories = @("config", "logs", "data")

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Host "✅ Created $dir directory" -ForegroundColor Green
    }
}

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "`n⚠️  .env file not found!" -ForegroundColor Yellow
    Write-Host "Please create .env file with your broker credentials." -ForegroundColor Yellow
    Write-Host "`nExample .env content:" -ForegroundColor Cyan
    Write-Host @"
# Upstox Account
UPSTOX_API_KEY=your_api_key
UPSTOX_API_SECRET=your_api_secret
UPSTOX_ACCESS_TOKEN=your_access_token
UPSTOX_ACCOUNT_NAME=YourName

# Dhan Account
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token
DHAN_ACCOUNT_NAME=YourName
"@
} else {
    Write-Host "✅ .env file found" -ForegroundColor Green
}

# Create virtual environment if not exists
if (-not (Test-Path "venv")) {
    Write-Host "`n📦 Creating virtual environment..." -ForegroundColor Cyan
    python -m venv venv
    Write-Host "✅ Virtual environment created" -ForegroundColor Green
    
    Write-Host "`n📥 Installing dependencies..." -ForegroundColor Cyan
    & ".\venv\Scripts\Activate.ps1"
    pip install -r requirements.txt
    Write-Host "✅ Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "✅ Virtual environment already exists" -ForegroundColor Green
}

Write-Host "`n" + ("="*60) -ForegroundColor Cyan
Write-Host "🎉 SETUP COMPLETE!" -ForegroundColor Green
Write-Host ("="*60) -ForegroundColor Cyan
Write-Host "`nTo run Traderchamp:" -ForegroundColor Yellow
Write-Host "1. Activate virtual environment: .\venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "2. Run application: python traderchamp.py" -ForegroundColor White
Write-Host "`nEnjoy trading! 🚀" -ForegroundColor Cyan
