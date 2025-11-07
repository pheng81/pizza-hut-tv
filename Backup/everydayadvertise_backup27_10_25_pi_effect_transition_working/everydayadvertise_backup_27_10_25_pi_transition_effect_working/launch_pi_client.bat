@echo off
REM Pizza Hut TV Pi Client Launcher
REM Launch the Pi client with GUI for easy management

echo Starting Pizza Hut TV Pi Client...
echo ====================================

cd /d "C:\Users\toeng\Pizza Hut TV"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Launch Pi client with GUI
echo Launching Pi Client GUI...
python pi_client.py

pause