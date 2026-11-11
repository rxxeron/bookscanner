@echo off
:: Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges to unblock Windows Firewall...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo ========================================================
echo   Configuring Windows Defender Firewall for Book Scanner...
echo ========================================================
netsh advfirewall firewall add rule name="Book Scanner (Ports 5000-5001)" dir=in action=allow protocol=TCP localport=5000,5001 profile=any
netsh advfirewall firewall set rule name="python.exe" new profile=any >nul 2>&1
echo.
echo ========================================================
echo  [SUCCESS] Ports 5000 and 5001 are now open!
echo  Phones on your Wi-Fi will now connect without timeout.
echo ========================================================
echo.
pause
