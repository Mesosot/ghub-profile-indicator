"""Opt-in Windows startup for the current user only; no administrator rights."""
from pathlib import Path
import subprocess
import sys
import winreg

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'GHubProfileIndicator'


def launch_command(port=9010, db=None):
    executable = Path(sys.executable).resolve()
    if getattr(sys, 'frozen', False):
        args = [str(executable)]
    else:
        pythonw = executable.with_name('pythonw.exe')
        args = [str(pythonw if pythonw.exists() else executable),
                str(Path(__file__).resolve().with_name('app.py'))]
    args += ['--port', str(port)]
    if db is not None:
        args += ['--db', str(Path(db).resolve())]
    return subprocess.list2cmdline(args)


def is_enabled(key_path=RUN_KEY):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            value, kind = winreg.QueryValueEx(key, VALUE_NAME)
            return kind == winreg.REG_SZ and bool(value)
    except FileNotFoundError:
        return False


def set_enabled(enabled, command, key_path=RUN_KEY):
    if enabled:
        if not command or len(command) > 260:
            raise ValueError('The startup command is too long. Move the app to a shorter folder path and try again.')
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
    else:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, VALUE_NAME)
        except FileNotFoundError:
            pass
