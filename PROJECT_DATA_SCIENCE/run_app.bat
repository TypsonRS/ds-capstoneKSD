@echo off
rem AgroRestore AI - start the Streamlit web app at https://agrorestoreai
rem Easiest: double-click "Start AgroRestore AI" (no console window). This .bat does the same from a terminal.
rem The app runs as a hidden background process, independent of this window, the notebook and VS Code.
rem Stop it: double-click "Stop AgroRestore AI" (or: run_app.bat stop). Messages go to streamlit.log.
rem One-time setup: setup_hostname.bat (as administrator) and trust_cert.bat.
"%~dp0venv\Scripts\python.exe" "%~dp0app\launcher.py" %*
