@echo off
REM Pizza Hut TV - Windows Pi Setup Helper
REM Helps transfer Pi installer to Raspberry Pi

echo.
echo 🍕 Pizza Hut TV - Pi Setup Helper for Windows
echo =============================================
echo.

if not exist "setup-pi.sh" (
    echo ❌ setup-pi.sh not found!
    echo    Make sure you're in the Pizza Hut TV directory
    pause
    exit /b 1
)

echo This helper will show you how to transfer the Pi installer to your Raspberry Pi.
echo.

echo 📋 METHOD 1: Using SCP (if you have SSH access)
echo ------------------------------------------------
echo scp setup-pi.sh pi@YOUR_PI_IP:/home/pi/
echo ssh pi@YOUR_PI_IP
echo chmod +x setup-pi.sh
echo ./setup-pi.sh
echo.

echo 📋 METHOD 2: Using USB drive
echo -----------------------------
echo 1. Copy setup-pi.sh to a USB drive
echo 2. Insert USB drive into Pi
echo 3. On Pi terminal:
echo    sudo mount /dev/sda1 /mnt
echo    cp /mnt/setup-pi.sh ~/
echo    chmod +x setup-pi.sh
echo    ./setup-pi.sh
echo.

echo 📋 METHOD 3: Direct download on Pi
echo ----------------------------------
echo On your Raspberry Pi terminal, run:
echo curl -sSL https://raw.githubusercontent.com/pheng81/pizza-hut-tv/main/setup-pi.sh ^| bash
echo.

echo 🔧 CONFIGURATION REMINDER:
echo After installation, edit the config file on Pi:
echo nano ~/pizza-hut-tv-pi/phtv-config
echo.
echo Set your server details:
echo PHTV_SERVER="http://YOUR_SERVER_IP:5002"
echo PHTV_STORE="YOUR_STORE_ID"  
echo PHTV_SCREEN="tv1"
echo.

pause