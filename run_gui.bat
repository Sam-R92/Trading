@echo off
echo Starting TraderChamp GUI...
cd /d "%~dp0"
call venv\Scripts\activate.bat
python traderchamp_gui.py
pause
