"""Small Windows desktop overlay. Source run: python app.py"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

from reader import Agent, DEFAULT_DB, read_catalog, sample

HOME = Path(os.environ.get('LOCALAPPDATA', '.')) / 'GHubIndicator'
CONFIG = HOME / 'config.json'
BG = '#202226'


def load_config():
    try:
        value = json.loads(CONFIG.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


class Indicator:
    def __init__(self, args):
        self.args, self.config = args, load_config()
        self.events = queue.Queue(maxsize=32)
        self.commands = queue.Queue()
        self.stop = threading.Event()
        self.tray = None
        self.previous = None
        self.current = None
        self.last_update = 0
        self.hidden = False
        self.drag = None
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title('G HUB Profile Indicator')
        self.root.configure(bg=BG)
        self.root.overrideredirect(not args.qa_window)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.96)
        # Clamp restored coordinates to the primary display if the old monitor disappeared.
        x = max(0, min(int(self.config.get('x', 40)), self.root.winfo_screenwidth()-380))
        y = max(0, min(int(self.config.get('y', 80)), self.root.winfo_screenheight()-150))
        self.root.geometry(f'380x122+{x}+{y}')
        self.frame = tk.Frame(self.root, bg=BG, highlightbackground='#41464f', highlightthickness=1)
        self.frame.pack(fill='both', expand=True)
        self.heading = tk.Label(self.frame, text='●  G HUB  /  PROFILE', fg='#32b9ef', bg=BG,
                                font=('Segoe UI', 9, 'bold'), anchor='w')
        self.heading.place(x=16, y=10, width=300)
        self.button = tk.Label(self.frame, text='⋯', fg='#cbd0da', bg=BG, font=('Segoe UI', 18))
        self.button.place(x=337, y=3, width=30, height=28)
        self.label = tk.Label(self.frame, text='Connecting…', fg='#f6f7fa', bg=BG,
                              font=('Segoe UI', 13, 'bold'), anchor='w', wraplength=344, justify='left')
        self.label.place(x=16, y=36, width=348, height=48)
        self.detail = tk.Label(self.frame, text='Reading directly from G HUB', fg='#a6aebb', bg=BG,
                               font=('Segoe UI', 9), anchor='w')
        self.detail.place(x=16, y=92, width=348)
        self.notifications = tk.BooleanVar(value=bool(self.config.get('notifications', False)))
        self.tray_enabled = tk.BooleanVar(value=bool(self.config.get('tray', True)))
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label='Show / hide overlay', command=self.toggle_overlay)
        self.menu.add_checkbutton(label='Notify when profile changes', variable=self.notifications, command=self.save)
        self.menu.add_checkbutton(label='Tray icon', variable=self.tray_enabled, command=self.toggle_tray)
        self.menu.add_separator()
        self.menu.add_command(label='Connection details / limitations', command=self.about)
        self.menu.add_command(label='Reset position', command=lambda: self.root.geometry('+40+80'))
        self.menu.add_command(label='Quit', command=self.quit)
        for widget in (self.root, self.frame, self.heading, self.label, self.detail):
            widget.bind('<ButtonPress-1>', self.start_drag)
            widget.bind('<B1-Motion>', self.move_drag)
            widget.bind('<ButtonRelease-1>', lambda e: self.save())
            widget.bind('<Button-3>', self.popup)
        self.button.bind('<Button-1>', self.popup)
        self.root.bind('<Escape>', lambda e: self.quit())
        self.root.protocol('WM_DELETE_WINDOW', self.quit)
        self.root.update_idletasks()
        # Keep mouse clicks on this overlay from activating it and switching G HUB to Desktop.
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.GetParent.argtypes = [ctypes.c_void_p]
        user.GetParent.restype = ctypes.c_void_p
        user.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        hwnd = user.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        if not args.qa_window:
            user.SetWindowLongW(hwnd, -20, user.GetWindowLongW(hwnd, -20) | 0x08000000 | 0x80)
        self.root.deiconify()
        self.toggle_tray(save=False)
        threading.Thread(target=self.worker, daemon=True).start()
        self.root.after(100, self.pump)
        if args.smoke_seconds:
            self.root.after(int(args.smoke_seconds*1000), self.quit)

    def emit(self, event):
        try:
            self.events.put_nowait(event)
        except queue.Full:
            pass

    def worker(self):
        agent = Agent(self.args.port)
        catalog, refreshed = {}, 0
        delay = 1
        try:
            while not self.stop.is_set():
                try:
                    if time.monotonic()-refreshed > 5:
                        try:
                            catalog = read_catalog(self.args.db)
                        except Exception:
                            catalog = {}  # Never use an old catalog as proof of active state.
                        refreshed = time.monotonic()
                    result = sample(agent, catalog)
                    self.emit(('profile', result, time.monotonic()))
                    delay = 1
                except Exception as exc:
                    self.emit(('error', type(exc).__name__ + ': ' + str(exc)[:180], time.monotonic()))
                    agent.close()
                    delay = min(5, delay+1)
                self.stop.wait(delay)
        finally:
            agent.close()

    def pump(self):
        while True:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                break
            if command == 'quit':
                self.quit()
                return
            if command == 'toggle':
                self.toggle_overlay()
            if command == 'menu':
                if self.hidden:
                    self.toggle_overlay()
                try:
                    self.menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
                finally:
                    self.menu.grab_release()
        while True:
            try:
                kind, value, stamp = self.events.get_nowait()
            except queue.Empty:
                break
            self.last_update = stamp
            if kind == 'error':
                self.current = None
                self.error = value
                self.label.config(text='Profile unavailable')
                self.heading.config(fg='#f2b66e')
                self.detail.config(text='Waiting for G HUB • retrying automatically')
                if self.tray:
                    self.tray.title = 'G HUB profile unavailable'
                continue
            self.current = value
            self.error = ''
            self.label.config(text=value['label'])
            self.heading.config(fg='#32b9ef')
            note = ('Onboard mode • software profile only' if value['onboard'] else
                    'No active device • software profile only' if not value['device_count'] else
                    'Live from G HUB • read-only')
            self.detail.config(text=note)
            if self.tray:
                self.tray.title = ('G HUB — ' + value['label'])[:127]
            if self.previous is not None and self.previous != value['id'] and self.notifications.get():
                self.notify(value['label'])
            self.previous = value['id']
        if self.last_update and time.monotonic()-self.last_update > 7:
            self.current = None
            self.label.config(text='Profile unavailable')
            self.detail.config(text='Live response expired • retrying')
        self.root.after(100, self.pump)

    def notify(self, text):
        if self.tray:
            try:
                self.tray.notify(text, 'G HUB profile changed')
                return
            except Exception:
                pass
        # Also works without a tray; no focus is requested.
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes('-topmost', True)
        toast.configure(bg=BG)
        tk.Label(toast, text='G HUB profile changed\n' + text, font=('Segoe UI', 11),
                 fg='white', bg=BG, padx=20, pady=14, wraplength=320).pack()
        toast.geometry(f'+{max(0,self.root.winfo_screenwidth()-380)}+60')
        toast.after(2800, toast.destroy)

    def toggle_tray(self, save=True):
        if self.tray_enabled.get() and self.tray is None:
            try:
                from win_tray import Tray
                self.tray = Tray(self.commands)
                self.tray.run_detached()
            except Exception:
                self.tray = None
                self.tray_enabled.set(False)
        elif not self.tray_enabled.get() and self.tray:
            self.tray.stop()
            self.tray = None
            if self.hidden:
                self.toggle_overlay()
        if save:
            self.save()

    def toggle_overlay(self):
        if not self.tray and not self.hidden:
            messagebox.showinfo('Tray icon needed', 'Enable the tray icon before hiding the overlay.', parent=self.root)
            return
        self.hidden = not self.hidden
        if self.hidden:
            self.root.withdraw()
        else:
            self.root.deiconify()

    def popup(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def start_drag(self, event):
        self.drag = (event.x_root-self.root.winfo_x(), event.y_root-self.root.winfo_y())

    def move_drag(self, event):
        if self.drag:
            x, y = event.x_root-self.drag[0], event.y_root-self.drag[1]
            self.root.geometry(f'+{max(0,x)}+{max(0,y)}')

    def save(self):
        try:
            HOME.mkdir(parents=True, exist_ok=True)
            value = {'x': self.root.winfo_x(), 'y': self.root.winfo_y(),
                     'notifications': self.notifications.get(), 'tray': self.tray_enabled.get()}
            temp = CONFIG.with_suffix('.tmp')
            temp.write_text(json.dumps(value), encoding='utf-8')
            temp.replace(CONFIG)
        except OSError:
            pass

    def about(self):
        value = self.current
        text = ('Source: G HUB agent, GET /profile/effective\n'
                'Transport: loopback WebSocket, port ' + str(self.args.port) + '\n'
                'Application names: read-only settings.db catalog\n\n'
                'This is a verified private interface, not an officially supported Logitech API. '
                'Updates can break it. No foreground-app prediction is used.\n\n'
                'Reports G HUB software state, not proof of the settings applied by a physical device. '
                'Onboard profiles, device-specific overrides and G-Shift are not displayed. '
                'Exclusive fullscreen games may cover the overlay.\n\n')
        if value:
            text += 'Reported profile: ' + value['label'] + '\nID: ' + value['id']
            if value['onboard']:
                text += '\nOnboard devices: ' + ', '.join(value['onboard'])
        else:
            text += 'Last error: ' + getattr(self, 'error', 'Waiting for response')
        messagebox.showinfo('G HUB Profile Indicator', text, parent=self.root)

    def quit(self):
        self.save()
        self.stop.set()
        if self.tray:
            self.tray.stop()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description='Read G HUB live profile; never infer from foreground apps.')
    parser.add_argument('--port', type=int, default=9010)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--diagnose', type=Path, help='Write a minimal local live-read report and exit')
    parser.add_argument('--smoke-seconds', type=float, default=0, help=argparse.SUPPRESS)
    parser.add_argument('--qa-window', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    if args.diagnose:
        agent = Agent(args.port)
        try:
            value = sample(agent, read_catalog(args.db))
            value.update(source='G HUB agent /profile/effective', read_only=True)
            args.diagnose.write_text(json.dumps(value, indent=2), encoding='utf-8')
        except Exception as exc:
            args.diagnose.write_text(json.dumps({'error': str(exc)}), encoding='utf-8')
            raise SystemExit(1)
        finally:
            agent.close()
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    # One overlay per Windows session. Keep the handle alive until exit.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel.CreateMutexW(None, False, 'Local\\GHubIndicatorOverlayV1')
    if not handle:
        raise OSError(ctypes.get_last_error(), 'Could not create app mutex')
    if ctypes.get_last_error() == 183:
        ctypes.windll.user32.MessageBoxW(None, 'The indicator is already running. Check its tray icon.', 'G HUB Indicator', 0)
        return
    try:
        Indicator(args).root.mainloop()
    finally:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)


if __name__ == '__main__':
    main()
