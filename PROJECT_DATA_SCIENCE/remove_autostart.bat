@echo off
rem AgroRestore AI - undo install_autostart.bat: the app no longer starts at Windows logon.
rem A running app is not stopped; close the "AgroRestore AI app" window for that.
set TARGET=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\AgroRestoreAI.cmd
if exist "%TARGET%" (
    del "%TARGET%"
    echo Removed: "%TARGET%"
) else (
    echo Nothing to do: autostart was not installed.
)
echo.
pause
