@echo off
rem AgroRestore AI - undo install_autostart.bat: the app no longer starts at Windows logon.
rem A running app is not stopped; double-click "Stop AgroRestore AI" for that.
"%~dp0venv\Scripts\python.exe" "%~dp0app\launcher.py" remove-autostart
pause
