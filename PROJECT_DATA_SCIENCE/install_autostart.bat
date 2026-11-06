@echo off
rem AgroRestore AI - start the app automatically every time you log in to Windows, so
rem https://agrorestoreai works without opening VS Code or a terminal. No administrator rights needed.
rem It puts a small script in your Startup folder that runs run_app.bat, and starts the app now.
rem Undo: remove_autostart.bat (or delete the file from the Startup folder).
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set TARGET=%STARTUP%\AgroRestoreAI.cmd

if not exist "%STARTUP%" mkdir "%STARTUP%"
> "%TARGET%" echo @echo off
>>"%TARGET%" echo rem AgroRestore AI autostart - created by install_autostart.bat; delete this file to undo.
>>"%TARGET%" echo call "%~dp0run_app.bat"
if errorlevel 1 (
    echo Could not write "%TARGET%".
    goto end
)
echo Installed: "%TARGET%"
echo The app will start at every Windows logon. Starting it now ...
echo.
call "%~dp0run_app.bat"

:end
echo.
pause
