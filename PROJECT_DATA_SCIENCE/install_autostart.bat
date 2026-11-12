@echo off
rem AgroRestore AI - start the app silently (no window) every time you log in to Windows, so
rem https://agrorestoreai works without opening VS Code or a terminal. No administrator rights needed.
rem Undo: remove_autostart.bat
"%~dp0venv\Scripts\python.exe" "%~dp0app\launcher.py" autostart
"%~dp0venv\Scripts\python.exe" "%~dp0app\launcher.py" --no-browser
pause
