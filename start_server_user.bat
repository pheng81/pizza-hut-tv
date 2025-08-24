@echo off
set "MEDIA_BASE_URL=https://api.everydayadvertise.com"
cd /d "C:\Users\toeng\Pizza Hut TV"
set "LOG=%cd%\server.log"
echo [%date% %time%] Starting Flask >> "%LOG%"
"C:\Users\toeng\Pizza Hut TV\.venv\Scripts\python.exe" "C:\Users\toeng\Pizza Hut TV\app.py" >> "%LOG%" 2>&1
