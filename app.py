"""Small Windows desktop overlay. Source run: python app.py"""
import argparse
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox

from reader import Agent, DEFAULT_DB, read_catalog, sample
from app_info import APP_NAME, VERSION
import startup

HOME = Path(os.environ.get('LOCALAPPDATA', '.')) / 'GHubIndicator'
CONFIG = HOME / 'config.json'
BG = '#202226'
COMPACT_SIZE = 46
COMPACT_DIMENSIONS = (112, 68)
EXPANDED_SIZE = (380, 122)
COLLAPSE_DELAY_MS = 10_000
PROFILE_CHANGE_DELAY_MS = 5_000


def desktop_work_area(x, y):
    """Use the monitor containing the anchor, including monitors at negative coordinates."""
    class MonitorInfo(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                    ('work', wintypes.RECT), ('flags', wintypes.DWORD)]
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
    user.MonitorFromPoint.restype = wintypes.HANDLE
    user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    monitor = user.MonitorFromPoint(wintypes.POINT(round(x), round(y)), 2)
    info = MonitorInfo()
    info.size = ctypes.sizeof(info)
    if not user.GetMonitorInfoW(monitor, ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    return info.work.left, info.work.top, info.work.right, info.work.bottom


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
        self.drag_origin = None
        self.drag_moved = False
        self.expanded = False
        self.animating = False
        self.animation_job = None
        self.collapse_job = None
        self.collapse_delay_ms = COLLAPSE_DELAY_MS
        self.profile_change_pending = False
        self.pump_job = None
        self.glass_job = None
        self.glass_renderer = None
        self.glass_presenter = None
        self.glass_signature = None
        self.glass_art_key = None
        self.glass_artwork = None
        self.menu_open = False
        self.hover_locked = False
        self.island_size = COMPACT_DIMENSIONS
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(APP_NAME)
        self.root.configure(bg=BG)
        self.root.overrideredirect(not args.qa_window)
        self.root.attributes('-topmost', True)
        # Restore on the selected monitor; recover to the nearest monitor if it was removed.
        self.compact_anchor = (int(self.config.get('x', 40)), int(self.config.get('y', 80)))
        x, y = self.position_for_size(*COMPACT_DIMENSIONS)
        self.compact_anchor = (x+(COMPACT_DIMENSIONS[0]-COMPACT_SIZE)//2, y)
        self.window_position = (x, y)
        self.root.geometry(f'{COMPACT_DIMENSIONS[0]}x{COMPACT_DIMENSIONS[1]}+{x}+{y}')
        self.frame = tk.Frame(self.root, bg=BG)
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
        self.compact = tk.Frame(self.frame, bg=BG, cursor='hand2')
        self.compact_icon = tk.Label(self.compact, text='G', fg='#32b9ef', bg=BG,
                                     font=('Segoe UI', 15, 'bold'), cursor='hand2')
        self.compact_icon.place(relx=0.5, x=-COMPACT_SIZE//2, y=0,
                                width=COMPACT_SIZE, height=COMPACT_SIZE)
        self.caption_font = tkfont.Font(family='Segoe UI', size=7)
        self.compact_caption = tk.Label(self.compact, text='Connecting…', fg='#d7dce5', bg=BG,
                                        font=self.caption_font, cursor='hand2')
        self.compact_caption.place(relx=0.5, x=-COMPACT_DIMENSIONS[0]//2, y=48,
                                   width=COMPACT_DIMENSIONS[0], height=18)
        self.compact.place(x=0, y=0, relwidth=1, relheight=1)
        self.compact.lift()
        self.notifications = tk.BooleanVar(value=bool(self.config.get('notifications', False)))
        self.tray_enabled = tk.BooleanVar(value=bool(self.config.get('tray', True)))
        try:
            startup_enabled = startup.is_enabled()
        except OSError:
            startup_enabled = False
        self.startup_enabled = tk.BooleanVar(value=startup_enabled)
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label='Expand profile', command=self.expand)
        self.menu.add_command(label='Collapse now', command=self.collapse_from_menu)
        self.menu.bind('<Unmap>', self.menu_closed)
        self.menu.add_command(label='Show / hide overlay', command=self.toggle_overlay)
        self.menu.add_checkbutton(label='Notify when profile changes', variable=self.notifications, command=self.save)
        self.menu.add_checkbutton(label='Tray icon', variable=self.tray_enabled, command=self.toggle_tray)
        self.menu.add_checkbutton(label='Start with Windows', variable=self.startup_enabled, command=self.toggle_startup)
        self.menu.add_separator()
        self.menu.add_command(label='Connection details / limitations', command=self.about)
        self.menu.add_command(label='Reset position', command=self.reset_position)
        self.menu.add_command(label='Quit', command=self.quit)
        for widget in (self.frame, self.heading, self.label, self.detail, self.compact,
                       self.compact_icon, self.compact_caption):
            widget.bind('<ButtonPress-1>', self.start_drag)
            widget.bind('<B1-Motion>', self.move_drag)
            widget.bind('<ButtonRelease-1>', self.end_drag)
            widget.bind('<Button-3>', self.popup)
            widget.bind('<Enter>', self.hover_expand)
        self.button.bind('<Button-1>', self.popup)
        self.root.bind('<Escape>', lambda e: self.quit())
        self.root.bind('<Leave>', self.hover_leave)
        self.root.protocol('WM_DELETE_WINDOW', self.quit)
        self.root.update_idletasks()
        # Keep mouse clicks on this overlay from activating it and switching G HUB to Desktop.
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.GetParent.argtypes = [ctypes.c_void_p]
        user.GetParent.restype = ctypes.c_void_p
        user.GetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int]
        user.SetWindowLongW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long]
        hwnd = user.GetParent(self.root.winfo_id()) or self.root.winfo_id()
        self.hwnd = hwnd
        self.user = user
        self.gdi = ctypes.WinDLL('gdi32', use_last_error=True)
        self.gdi.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
        self.gdi.CreateRoundRectRgn.restype = ctypes.c_void_p
        self.gdi.DeleteObject.argtypes = [ctypes.c_void_p]
        self.gdi.CombineRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
        self.user.SetWindowRgn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
        if not args.qa_window:
            user.SetWindowLongW(hwnd, -20, user.GetWindowLongW(hwnd, -20) | 0x08000000 | 0x80)
            from glass import GlassRenderer, LayeredWindow
            self.glass_renderer = GlassRenderer()
            self.glass_presenter = LayeredWindow(hwnd)
            self.root.bind('<Configure>', lambda event: self.request_glass())
        self.root.deiconify()
        self.round_window(*self.island_size)
        self.toggle_tray(save=False)
        threading.Thread(target=self.worker, daemon=True).start()
        self.pump_job = self.root.after(100, self.pump)
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
                self.show_menu(self.root.winfo_pointerx(), self.root.winfo_pointery())
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
                self.compact_icon.config(fg='#f2b66e')
                self.compact_caption.config(text='Unavailable', fg='#f2b66e')
                self.detail.config(text='Waiting for G HUB • retrying automatically')
                if self.tray:
                    self.tray.title = APP_NAME + ' — unavailable'
                continue
            self.current = value
            self.error = ''
            self.label.config(text=value['label'])
            self.heading.config(fg='#32b9ef')
            self.compact_icon.config(fg='#32b9ef')
            self.compact_caption.config(text=self.compact_text(value['label']), fg='#d7dce5')
            note = ('Onboard mode • software profile only' if value['onboard'] else
                    'No active device • software profile only' if not value['device_count'] else
                    'Live from G HUB • read-only')
            self.detail.config(text=note)
            if self.tray:
                self.tray.title = (APP_NAME + ' — ' + value['label'])[:127]
            if self.previous is not None and self.previous != value['id']:
                self.show_profile_change()
                if self.notifications.get():
                    self.notify(value['label'])
            self.previous = value['id']
        if self.last_update and time.monotonic()-self.last_update > 7:
            self.current = None
            self.label.config(text='Profile unavailable')
            self.detail.config(text='Live response expired • retrying')
            self.compact_icon.config(fg='#f2b66e')
            self.compact_caption.config(text='Unavailable', fg='#f2b66e')
        self.request_glass()
        self.pump_job = self.root.after(100, self.pump)

    def notify(self, text):
        if self.tray:
            try:
                self.tray.notify(text, APP_NAME)
                return
            except Exception:
                pass
        # Also works without a tray; no focus is requested.
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.attributes('-topmost', True)
        toast.configure(bg=BG)
        tk.Label(toast, text=APP_NAME + '\n' + text, font=('Segoe UI', 11),
                 fg='white', bg=BG, padx=20, pady=14, wraplength=320).pack()
        toast.geometry(f'+{max(0,self.root.winfo_screenwidth()-380)}+60')
        toast.after(2800, toast.destroy)

    def compact_text(self, label):
        available = COMPACT_DIMENSIONS[0]-10
        if self.caption_font.measure(label) <= available:
            return label
        text = label
        while text and self.caption_font.measure(text+'…') > available:
            text = text[:-1]
        return text+'…'

    def show_profile_change(self):
        # Keep tray-hidden windows hidden; show only the latest name on restore.
        if self.hidden:
            return
        if self.menu_open or self.drag:
            self.profile_change_pending = True
            return
        self.profile_change_pending = False
        if not self.expanded:
            self.animate_island(True)
        self.schedule_collapse(PROFILE_CHANGE_DELAY_MS)

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
            if self.expanded:
                self.schedule_collapse()

    def popup(self, event):
        self.show_menu(event.x_root, event.y_root)

    def show_menu(self, x, y):
        try:
            self.startup_enabled.set(startup.is_enabled())
        except OSError:
            pass
        self.menu_open = True
        if self.collapse_job:
            self.root.after_cancel(self.collapse_job)
            self.collapse_job = None
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    def menu_closed(self, event=None):
        self.menu_open = False
        if self.profile_change_pending:
            self.show_profile_change()
        elif self.expanded:
            self.schedule_collapse()

    def collapse_from_menu(self):
        self.profile_change_pending = False
        self.menu_open = False
        self.collapse()

    def round_window(self, width, height):
        if self.glass_renderer is not None:
            self.request_glass()
            return
        if self.args.qa_window:
            return
        if (width, height) == COMPACT_DIMENSIONS:
            left = (width-COMPACT_SIZE)//2
            region = self.gdi.CreateRoundRectRgn(left, 0, left+COMPACT_SIZE+1, COMPACT_SIZE+1,
                                                 COMPACT_SIZE, COMPACT_SIZE)
            caption = self.gdi.CreateRoundRectRgn(0, 48, width+1, height+1, 12, 12)
            if region and caption:
                self.gdi.CombineRgn(region, region, caption, 2)
            if caption:
                self.gdi.DeleteObject(caption)
        else:
            radius = min(height, 48)
            region = self.gdi.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius, radius)
        if region and not self.user.SetWindowRgn(self.hwnd, region, True):
            self.gdi.DeleteObject(region)

    def request_glass(self):
        if self.glass_renderer is not None and self.glass_job is None and not self.stop.is_set():
            self.glass_job = self.root.after_idle(self.draw_glass)

    def draw_glass(self):
        self.glass_job = None
        if self.hidden or self.stop.is_set():
            return
        width, height = self.island_size
        progress = max(0, min(1, (width-COMPACT_DIMENSIONS[0])/(EXPANDED_SIZE[0]-COMPACT_DIMENSIONS[0])))
        label = self.label.cget('text')
        detail = self.detail.cget('text')
        accent = (73, 210, 255) if self.compact_icon.cget('fg') == '#32b9ef' else (255, 184, 112)
        x, y = self.window_position
        signature = (width, height, label, detail, accent, x, y)
        if signature == self.glass_signature:
            return
        art_key = (width, height, label, detail, accent)
        if art_key != self.glass_art_key:
            self.glass_artwork = self.glass_renderer.render(width, height, progress, label, detail, accent)
            self.glass_art_key = art_key
        self.glass_presenter.present(self.glass_artwork, x, y)
        self.glass_signature = signature

    def hover_expand(self, event=None):
        if not self.expanded and not self.animating and not self.drag and not self.hover_locked:
            self.expand()

    def hover_leave(self, event=None):
        px, py = self.root.winfo_pointerxy()
        x, y = self.window_position
        width, height = self.island_size
        if not (x <= px < x+width and y <= py < y+height):
            self.hover_locked = False

    def schedule_collapse(self, delay_ms=None):
        if delay_ms is not None:
            self.collapse_delay_ms = delay_ms
        if self.collapse_job:
            self.root.after_cancel(self.collapse_job)
        self.collapse_job = self.root.after(self.collapse_delay_ms, self.collapse)

    def expand(self):
        self.profile_change_pending = False
        if not self.expanded:
            self.animate_island(True)
        self.schedule_collapse(COLLAPSE_DELAY_MS)

    def collapse(self):
        if self.collapse_job:
            self.root.after_cancel(self.collapse_job)
        self.collapse_job = None
        if self.menu_open or self.drag:
            self.schedule_collapse()
            return
        if self.expanded:
            self.hover_locked = True
            self.animate_island(False)

    def animate_island(self, expanding):
        if self.animation_job:
            self.root.after_cancel(self.animation_job)
        self.expanded = expanding
        self.animating = True
        start_w, start_h = self.island_size
        end_w, end_h = EXPANDED_SIZE if expanding else COMPACT_DIMENSIONS
        # Layout always comes from the user's saved compact anchor, never a pending
        # Tk geometry update or the temporarily clamped expanded window position.
        start_x, start_y = self.window_position
        end_x, end_y = self.position_for_size(end_w, end_h)
        began = time.monotonic()
        self.compact.lift()

        def frame():
            progress = min(1.0, (time.monotonic()-began)/0.36)
            # Critically damped motion: soft acceleration and settling, without jitter or overshoot.
            eased = (1-(1+8*progress)*math.exp(-8*progress))/(1-9*math.exp(-8))
            width = round(start_w+(end_w-start_w)*eased)
            height = round(start_h+(end_h-start_h)*eased)
            x = round(start_x+(end_x-start_x)*eased)
            y = round(start_y+(end_y-start_y)*eased)
            self.island_size = (width, height)
            self.window_position = (x, y)
            self.root.geometry(f'{width}x{height}+{x}+{y}')
            self.round_window(width, height)
            if expanding and progress > 0.65:
                self.compact.place_forget()
            if progress < 1:
                self.animation_job = self.root.after(15, frame)
            else:
                self.animation_job = None
                self.animating = False
                if not expanding:
                    self.compact.place(x=0, y=0, relwidth=1, relheight=1)
                    self.compact.lift()
                    self.root.after_idle(self.hover_leave)
                self.save()

        if not expanding:
            self.compact.place(x=0, y=0, relwidth=1, relheight=1)
        frame()

    def reset_position(self):
        if self.animation_job:
            self.root.after_cancel(self.animation_job)
            self.animation_job = None
            self.animating = False
        width, height = EXPANDED_SIZE if self.expanded else COMPACT_DIMENSIONS
        self.island_size = (width, height)
        self.compact_anchor = (40, 80)
        x, y = self.position_for_size(width, height)
        self.window_position = (x, y)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        self.round_window(width, height)
        self.save()

    def toggle_startup(self):
        enabled = self.startup_enabled.get()
        try:
            db = self.args.db if self.args.db != DEFAULT_DB else None
            startup.set_enabled(enabled, startup.launch_command(self.args.port, db))
        except (OSError, ValueError) as exc:
            self.startup_enabled.set(not enabled)
            messagebox.showerror('Windows startup', 'Could not update Windows startup:\n' + str(exc), parent=self.root)

    def start_drag(self, event):
        if self.animation_job:
            self.root.after_cancel(self.animation_job)
            self.animation_job = None
            self.animating = False
        self.drag = (event.x_root-self.window_position[0], event.y_root-self.window_position[1])
        self.drag_origin = (event.x_root, event.y_root)
        self.drag_moved = False

    def move_drag(self, event):
        if self.drag:
            if self.drag_origin and max(abs(event.x_root-self.drag_origin[0]), abs(event.y_root-self.drag_origin[1])) > 4:
                self.drag_moved = True
            x, y = event.x_root-self.drag[0], event.y_root-self.drag[1]
            self.window_position = (x, y)
            if self.drag_moved:
                self.compact_anchor = (x+(self.island_size[0]-COMPACT_SIZE)//2, y)
            self.root.geometry(f'+{x}+{y}')
            self.request_glass()

    def end_drag(self, event):
        moved = self.drag_moved
        self.drag = None
        self.drag_origin = None
        # Settle an animation interrupted by dragging before the next transition.
        target = EXPANDED_SIZE if self.expanded else COMPACT_DIMENSIONS
        if self.island_size != target:
            self.animate_island(self.expanded)
        if self.profile_change_pending:
            self.show_profile_change()
        elif not moved:
            self.expand()
        elif self.expanded:
            self.schedule_collapse()
        self.save()

    def save(self):
        try:
            HOME.mkdir(parents=True, exist_ok=True)
            value = {'x': self.compact_anchor[0], 'y': self.compact_anchor[1],
                     'notifications': self.notifications.get(), 'tray': self.tray_enabled.get()}
            temp = CONFIG.with_suffix('.tmp')
            temp.write_text(json.dumps(value), encoding='utf-8')
            temp.replace(CONFIG)
        except OSError:
            pass

    def position_for_size(self, width, height):
        circle_x, top = self.compact_anchor
        left, monitor_top, right, bottom = desktop_work_area(circle_x+COMPACT_SIZE/2, top+COMPACT_SIZE/2)
        x = round(circle_x+COMPACT_SIZE/2-width/2)
        return (max(left, min(x, right-width)),
                max(monitor_top, min(top, bottom-height)))

    def about(self):
        value = self.current
        text = (APP_NAME + ' ' + VERSION + '\n\nSource: G HUB agent, GET /profile/effective\n'
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
        messagebox.showinfo(APP_NAME, text, parent=self.root)

    def quit(self):
        for job in (self.animation_job, self.collapse_job, self.pump_job, self.glass_job):
            if job:
                self.root.after_cancel(job)
        self.save()
        self.stop.set()
        if self.tray:
            self.tray.stop()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=APP_NAME + ': read the live profile directly from G HUB.')
    parser.add_argument('--version', action='version', version=APP_NAME + ' ' + VERSION)
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
        ctypes.windll.user32.MessageBoxW(None, 'The indicator is already running. Check its tray icon.', APP_NAME, 0)
        return
    try:
        Indicator(args).root.mainloop()
    finally:
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel.CloseHandle(handle)


if __name__ == '__main__':
    main()
