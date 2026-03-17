# Toggle Performance Settings for FusionTrade
# Run this script to quickly enable/disable logging and debug prints

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('fast', 'debug', 'log-only')]
    [string]$Mode = 'fast'
)

$configFile = "traderchamp_gui.py"

if (-not (Test-Path $configFile)) {
    Write-Host "❌ Error: $configFile not found!" -ForegroundColor Red
    exit 1
}

Write-Host "`n🔧 FusionTrade Performance Configuration`n" -ForegroundColor Cyan

switch ($Mode) {
    'fast' {
        Write-Host "⚡ Setting MAXIMUM SPEED mode (Production)..." -ForegroundColor Green
        $logging = 'False'
        $debug = 'False'
        $description = "Fastest performance, no overhead"
    }
    'debug' {
        Write-Host "🐛 Setting DEBUG mode (Development)..." -ForegroundColor Yellow
        $logging = 'True'
        $debug = 'True'
        $description = "Full logging + debug prints"
    }
    'log-only' {
        Write-Host "📝 Setting LOG-ONLY mode (Testing)..." -ForegroundColor Magenta
        $logging = 'True'
        $debug = 'False'
        $description = "File logging only, no debug spam"
    }
}

# Read the file
$content = Get-Content $configFile -Raw

# Replace ENABLE_LOGGING
$content = $content -replace 'ENABLE_LOGGING\s*=\s*(True|False)', "ENABLE_LOGGING = $logging"

# Replace ENABLE_DEBUG_PRINTS
$content = $content -replace 'ENABLE_DEBUG_PRINTS\s*=\s*(True|False)', "ENABLE_DEBUG_PRINTS = $debug"

# Write back
$content | Set-Content $configFile -NoNewline

Write-Host "`n✅ Configuration Updated:" -ForegroundColor Green
Write-Host "   ENABLE_LOGGING = $logging" -ForegroundColor White
Write-Host "   ENABLE_DEBUG_PRINTS = $debug" -ForegroundColor White
Write-Host "`n📝 Description: $description" -ForegroundColor Cyan
Write-Host "`n💡 Restart the application for changes to take effect.`n" -ForegroundColor Yellow

# Show usage examples
Write-Host "📚 Usage Examples:" -ForegroundColor Cyan
Write-Host "   .\toggle_performance.ps1 fast       # Maximum speed (default)" -ForegroundColor White
Write-Host "   .\toggle_performance.ps1 debug      # Full debugging" -ForegroundColor White
Write-Host "   .\toggle_performance.ps1 log-only   # Logging without spam`n" -ForegroundColor White
