@echo off
rem AgroRestore AI - start the Streamlit web app at https://agrorestoreai
rem Double-click this file, or run it from a terminal. The app runs in this window
rem and keeps running after the notebook is closed. Close this window to stop it.
rem One-time setup: setup_hostname.bat (as administrator) and trust_cert.bat.
cd /d "%~dp0"

rem Self-signed certificate for agrorestoreai + localhost (created or refreshed by app\make_cert.py)
"%~dp0venv\Scripts\python.exe" "%~dp0app\make_cert.py"

echo Starting AgroRestore AI at https://agrorestoreai  (also https://localhost)
echo If the browser warns about the certificate, run trust_cert.bat once.
"%~dp0venv\Scripts\python.exe" -m streamlit run "%~dp0app\streamlit_app.py" --server.port 443 --server.headless true --server.sslCertFile "%~dp0certs\localhost.crt" --server.sslKeyFile "%~dp0certs\localhost.key"
echo.
echo Streamlit stopped. Read the messages above if it did not start.
pause
