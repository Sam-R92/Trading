# FusionTrade Lite - Build Script
# Builds standalone EXE using PyInstaller

Write-Host "🚀 Building FusionTrade Lite EXE..." -ForegroundColor Green

# Clean previous builds
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "*.spec") { Remove-Item -Force "*.spec" }

# Build EXE
pyinstaller `
    --name="FusionTradeLite" `
    --onefile `
    --windowed `
    --icon=NONE `
    --add-data="brokers;brokers" `
    --add-data="config;config" `
    --hidden-import=tkinter `
    --hidden-import=requests `
    --noconsole `
    traderchamp_lite.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Build successful! EXE created in dist\ folder" -ForegroundColor Green
    Write-Host "📦 File: dist\FusionTradeLite.exe" -ForegroundColor Cyan
    
    # Show file size
    $exeSize = (Get-Item "dist\FusionTradeLite.exe").Length / 1MB
    Write-Host "📊 Size: $([math]::Round($exeSize, 2)) MB" -ForegroundColor Yellow
} else {
    Write-Host "❌ Build failed!" -ForegroundColor Red
}
