"""Start or stop the AgroRestore AI web app in the background, without a console window.

    pythonw app/launcher.py              start the app (if needed) and open https://agrorestoreai
    pythonw app/launcher.py --no-browser start the app only (used by the Windows autostart)
    pythonw app/launcher.py stop         stop the app
    python  app/launcher.py shortcuts    create the double-click shortcuts (Windows)

The server runs as a hidden background process that keeps running after the notebook, VS Code or
the terminal is closed. Its messages go to streamlit.log in PROJECT_DATA_SCIENCE.
Only the standard library is used here, so this file runs with any Python.
"""

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent            # PROJECT_DATA_SCIENCE
WINDOWS = sys.platform == "win32"
PYTHON = ROOT / "venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
PYTHONW = ROOT / "venv" / "Scripts" / "pythonw.exe"
PORT = 443                                               # https://agrorestoreai (no port in the URL)
URL = "https://agrorestoreai"                            # set by setup_hostname.bat; https://localhost works too
LOG = ROOT / "streamlit.log"
CERTS = ROOT / "certs"

NO_WINDOW = 0x08000000 if WINDOWS else 0                 # CREATE_NO_WINDOW
NEW_GROUP = 0x00000200 if WINDOWS else 0                 # CREATE_NEW_PROCESS_GROUP
BREAKAWAY = 0x01000000 if WINDOWS else 0                 # CREATE_BREAKAWAY_FROM_JOB: survive VS Code closing


def say(msg: str, error: bool = False) -> None:
    """Print, or show a message box when there is no console (pythonw)."""
    if sys.stdout is not None:
        print(msg, file=sys.stderr if error else sys.stdout)
    elif WINDOWS and error:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "AgroRestore AI", 0x10)


def running() -> bool:
    try:
        socket.create_connection(("localhost", PORT), timeout=1).close()
        return True
    except OSError:
        return False


def start(open_browser: bool = True) -> None:
    if running():
        say(f"AgroRestore AI is already running at {URL}")
    else:
        log = open(LOG, "w")
        # Self-signed certificate for agrorestoreai + localhost (created or refreshed when needed)
        subprocess.run([str(PYTHON), str(ROOT / "app" / "make_cert.py")], cwd=ROOT, stdout=log,
                       stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
        cmd = [str(PYTHON), "-m", "streamlit", "run", str(ROOT / "app" / "streamlit_app.py"),
               "--server.port", str(PORT), "--server.headless", "true",
               "--server.sslCertFile", str(CERTS / "localhost.crt"),
               "--server.sslKeyFile", str(CERTS / "localhost.key")]
        kwargs = dict(cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, close_fds=True)
        if WINDOWS:
            try:
                subprocess.Popen(cmd, creationflags=NO_WINDOW | NEW_GROUP | BREAKAWAY, **kwargs)
            except OSError:                              # the parent's job does not allow breakaway
                subprocess.Popen(cmd, creationflags=NO_WINDOW | NEW_GROUP, **kwargs)
        else:
            subprocess.Popen(cmd, start_new_session=True, **kwargs)
        for _ in range(60):                              # wait until the server accepts connections
            if running():
                break
            time.sleep(1)
        else:
            say(f"AgroRestore AI did not start within 60 s.\nSee {LOG}", error=True)
            sys.exit(1)
        say(f"AgroRestore AI running at {URL} in the background (log: {LOG.name})")
    if open_browser:
        webbrowser.open(URL)


def listening_pids() -> set:
    """PIDs of the processes listening on PORT."""
    if WINDOWS:
        out = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True,
                             creationflags=NO_WINDOW).stdout
        return {line.split()[-1] for line in out.splitlines()
                if "LISTENING" in line and line.split()[1].endswith(f":{PORT}")}
    out = subprocess.run(["lsof", "-ti", f"tcp:{PORT}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
    return set(out.split())


def stop() -> None:
    pids = listening_pids()
    if not pids:
        say("AgroRestore AI is not running.")
        return
    for pid in pids:
        if WINDOWS:
            subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
        else:
            subprocess.run(["kill", pid])
    say("AgroRestore AI stopped.")


def make_shortcut(path: Path, args: str, description: str) -> None:
    """Windows .lnk that runs pythonw.exe, so double-clicking it opens no console window."""
    ps = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LNK); "
          "$s.TargetPath = $env:TGT; $s.Arguments = $env:ARGS; $s.WorkingDirectory = $env:WD; "
          "$s.Description = $env:DESC; $s.IconLocation = \"$env:SystemRoot\\System32\\shell32.dll,13\"; $s.Save()")
    env = dict(os.environ, LNK=str(path), TGT=str(PYTHONW), ARGS=args, WD=str(ROOT), DESC=description)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, check=True, creationflags=NO_WINDOW)
    say(f"Created {path}")


ME = f'"{Path(__file__).resolve()}"'
STARTUP = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def shortcuts() -> None:
    make_shortcut(ROOT / "Start AgroRestore AI.lnk", ME, "Start the AgroRestore AI app and open it in the browser")
    make_shortcut(ROOT / "Stop AgroRestore AI.lnk", f"{ME} stop", "Stop the AgroRestore AI app")


def autostart(enable: bool) -> None:
    """Start the app silently at every Windows logon (a shortcut in the Startup folder)."""
    (STARTUP / "AgroRestoreAI.cmd").unlink(missing_ok=True)   # older version, opened a cmd window
    lnk = STARTUP / "AgroRestoreAI.lnk"
    if enable:
        make_shortcut(lnk, f"{ME} --no-browser", "Start the AgroRestore AI app in the background")
    else:
        lnk.unlink(missing_ok=True)
        say(f"Removed {lnk}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "stop" in args:
        stop()
    elif "shortcuts" in args:
        shortcuts()
    elif "autostart" in args:
        autostart(True)
    elif "remove-autostart" in args:
        autostart(False)
    else:
        start(open_browser="--no-browser" not in args)
