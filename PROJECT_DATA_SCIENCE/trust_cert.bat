@echo off
rem AgroRestore AI - make this Windows user trust the app's self-signed certificate,
rem so https://agrorestoreai (and https://localhost) opens without a browser warning.
rem Run it once (double-click or from a terminal) and click "Yes" in the Windows dialog.
rem Undo with:  certutil -delstore -user Root agrorestoreai
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" "%~dp0app\make_cert.py"
rem remove an older copy of the certificate (issued to "localhost" before the app got its own name)
certutil -delstore -user Root localhost >nul 2>&1
certutil -addstore -user Root "%~dp0certs\localhost.crt"
echo.
if errorlevel 1 (
    echo The certificate was NOT installed. If you clicked "No", run this file again and click "Yes".
) else (
    echo Done. Close and reopen your browser, then open https://agrorestoreai
)
pause
