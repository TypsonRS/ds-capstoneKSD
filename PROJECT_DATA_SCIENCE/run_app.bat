@echo off
rem AgroRestore AI - start the Streamlit web app at https://agrorestoreai
rem Double-click this file, or run it from any terminal (VS Code's included). The app runs in
rem its OWN minimised window, "AgroRestore AI app", so it keeps running after the terminal, the
rem notebook or VS Code is closed. Close that window (taskbar) to stop the app.
rem One-time setup: setup_hostname.bat (as administrator) and trust_cert.bat.
rem Start at every Windows logon: install_autostart.bat (undo: remove_autostart.bat).
setlocal
cd /d "%~dp0"
set URL=https://agrorestoreai

if "%~1"=="--serve" goto serve

call :running
if not errorlevel 1 (
    echo AgroRestore AI is already running at %URL%
    goto done
)

rem Launch this script again in a window of its own, independent of the one we are in
rem (Start-Process hands the new window no handles of ours, so nothing waits for it).
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -WindowStyle Minimized -FilePath $env:ComSpec -ArgumentList '/c \"\"%~f0\" --serve\"'"
echo Starting AgroRestore AI in its own window, "AgroRestore AI app" ^(minimised in the taskbar^) ...
for /l %%i in (1,1,60) do (
    call :running
    if not errorlevel 1 goto started
    ping -n 2 127.0.0.1 >nul
)
echo The app did not start within 60 s. Look at the "AgroRestore AI app" window for the error.
goto done

:started
echo Running at %URL%  ^(also https://localhost^). Close the "AgroRestore AI app" window to stop it.
goto done

:done
rem Give a double-clicker time to read the message; a terminal gets the prompt back right away.
echo %cmdcmdline% | findstr /i /c:"/c" >nul 2>&1 && ping -n 7 127.0.0.1 >nul
exit /b 0

:running
rem errorlevel 0 when something already listens on port 443
netstat -ano -p tcp | findstr /r /c:":443 .*LISTENING" >nul 2>&1
exit /b %errorlevel%

:serve
title AgroRestore AI app
rem Self-signed certificate for agrorestoreai + localhost (created or refreshed by app\make_cert.py)
"%~dp0venv\Scripts\python.exe" "%~dp0app\make_cert.py"

echo Starting AgroRestore AI at %URL%  (also https://localhost)
echo If the browser warns about the certificate, run trust_cert.bat once.
"%~dp0venv\Scripts\python.exe" -m streamlit run "%~dp0app\streamlit_app.py" --server.port 443 --server.headless true --server.sslCertFile "%~dp0certs\localhost.crt" --server.sslKeyFile "%~dp0certs\localhost.key"
echo.
echo Streamlit stopped. Read the messages above if it did not start.
pause
