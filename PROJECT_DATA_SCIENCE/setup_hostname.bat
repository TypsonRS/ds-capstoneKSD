@echo off
rem AgroRestore AI - point the name "agrorestoreai" at this computer, so the app opens at
rem https://agrorestoreai instead of https://localhost:8501.
rem It adds one line to the Windows hosts file, which needs administrator rights:
rem right-click this file and choose "Run as administrator". Run it once.
rem Undo: delete the line "127.0.0.1 agrorestoreai" from C:\Windows\System32\drivers\etc\hosts
set HOSTS=%SystemRoot%\System32\drivers\etc\hosts
set NAME=agrorestoreai

findstr /i /r /c:"^[^#]*[ \t]%NAME%\([ \t]\|$\)" "%HOSTS%" >nul 2>&1
if not errorlevel 1 (
    echo "%NAME%" is already in the hosts file. Nothing to do.
    goto :end
)

net session >nul 2>&1
if errorlevel 1 (
    echo This needs administrator rights: right-click setup_hostname.bat and choose "Run as administrator".
    goto :end
)

>>"%HOSTS%" echo.
>>"%HOSTS%" echo 127.0.0.1 %NAME%
>>"%HOSTS%" echo ::1 %NAME%
if errorlevel 1 (
    echo Could not write to the hosts file.
) else (
    echo Added "%NAME%" to the hosts file. Next: run trust_cert.bat once, then run_app.bat and open https://%NAME%
)

:end
echo.
pause
