@echo off
echo Transferring enhanced Pi client to Raspberry Pi...
echo.

REM Create a temporary script for expect-like behavior
echo set timeout 20 > temp_expect.exp
echo spawn scp phtv_pi_client.py everydayadvertise@raspberrypi:/home/everydayadvertise/ >> temp_expect.exp
echo expect "password:" >> temp_expect.exp
echo send "pheng168\r" >> temp_expect.exp
echo expect eof >> temp_expect.exp

REM Try using expect if available
expect temp_expect.exp

if %errorlevel% equ 0 (
    echo ✅ Pi client updated successfully!
    echo The EA TV icon will now use enhanced synchronization
    
    REM Try to restart EA TV process
    echo Restarting EA TV process...
    ssh everydayadvertise@raspberrypi "pkill -f phtv_pi_client.py || true"
    
    echo ✅ Deployment complete!
) else (
    echo ❌ Automated transfer failed. Please follow manual instructions in PI_UPDATE_INSTRUCTIONS.md
    echo.
    echo Quick manual steps:
    echo 1. Open WinSCP or similar file transfer tool
    echo 2. Connect to raspberrypi with user: everydayadvertise, password: pheng168
    echo 3. Upload phtv_pi_client.py to /home/everydayadvertise/
    echo 4. Click EA TV icon to test
)

REM Cleanup
del temp_expect.exp 2>nul

pause