@echo off
REM Windows Batch File to Start Trading Bot
REM Run this on Windows after installation

echo Starting Binance Trading Bot...
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found!
    echo Please run the installation script first.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Check if config file exists
if not exist "config_local.yaml" (
    echo Error: Configuration file not found!
    echo Please create config_local.yaml first.
    pause
    exit /b 1
)

REM Start the bot
echo Starting bot in live mode...
echo Dashboard will be available at: http://localhost:8000
echo Press Ctrl+C to stop the bot
echo.

python run.py --mode live --verbose

pause
