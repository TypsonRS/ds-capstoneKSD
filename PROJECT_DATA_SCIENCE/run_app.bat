@echo off
rem AgroRestore AI - start the Streamlit web app.
rem Double-click this file, or run it from a terminal. The app runs in this window
rem and keeps running after the notebook is closed. Close this window to stop it.
cd /d "%~dp0"
echo Starting AgroRestore AI at http://localhost:8501 ...
"%~dp0venv\Scripts\python.exe" -m streamlit run "%~dp0app\streamlit_app.py" --server.port 8501 --server.headless true
echo.
echo Streamlit stopped. Read the messages above if it did not start.
pause
