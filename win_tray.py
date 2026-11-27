"""Minimal Windows notification-area icon; standard library only."""
import ctypes as c
from ctypes import wintypes as w
import threading
from app_info import APP_NAME

LRESULT = c.c_ssize_t
WNDPROC = c.WINFUNCTYPE(LRESULT, w.HWND, w.UINT, w.WPARAM, w.LPARAM)


class WNDCLASS(c.Structure):
    _fields_ = [('style', w.UINT), ('lpfnWndProc', WNDPROC), ('cbClsExtra', c.c_int),
                ('cbWndExtra', c.c_int), ('hInstance', w.HINSTANCE), ('hIcon', w.HICON),
                ('hCursor', w.HANDLE), ('hbrBackground', w.HBRUSH),
                ('lpszMenuName', w.LPCWSTR), ('lpszClassName', w.LPCWSTR)]


class NOTIFYICONDATA(c.Structure):
    _fields_ = [('cbSize', w.DWORD), ('hWnd', w.HWND), ('uID', w.UINT),
                ('uFlags', w.UINT), ('uCallbackMessage', w.UINT), ('hIcon', w.HICON),
                ('szTip', w.WCHAR*128), ('dwState', w.DWORD), ('dwStateMask', w.DWORD),
                ('szInfo', w.WCHAR*256), ('uTimeoutOrVersion', w.UINT),
                ('szInfoTitle', w.WCHAR*64), ('dwInfoFlags', w.DWORD),
                ('guidItem', c.c_byte*16), ('hBalloonIcon', w.HICON)]


class Tray:
    def __init__(self, commands):
        self.commands = commands
        self.hwnd = None
        self.ready = threading.Event()
        self.error = None
        self.lock = threading.Lock()
        self.user = c.WinDLL('user32', use_last_error=True)
        self.shell = c.WinDLL('shell32', use_last_error=True)
        self.kernel = c.WinDLL('kernel32', use_last_error=True)
        self.user.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        self.user.DefWindowProcW.restype = LRESULT
        self.user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
            c.c_int, c.c_int, c.c_int, c.c_int, w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p]
        self.user.CreateWindowExW.restype = w.HWND
        self.user.LoadIconW.argtypes = [w.HINSTANCE, c.c_void_p]
        self.user.LoadIconW.restype = w.HICON
        self.user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
        self.user.DestroyWindow.argtypes = [w.HWND]
        self.user.RegisterClassW.argtypes = [c.POINTER(WNDCLASS)]
        self.user.RegisterWindowMessageW.argtypes = [w.LPCWSTR]
        self.user.UnregisterClassW.argtypes = [w.LPCWSTR, w.HINSTANCE]
        self.user.GetMessageW.argtypes = [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT]
        self.user.TranslateMessage.argtypes = [c.POINTER(w.MSG)]
        self.user.DispatchMessageW.argtypes = [c.POINTER(w.MSG)]
        self.user.DispatchMessageW.restype = LRESULT
        self.shell.Shell_NotifyIconW.argtypes = [w.DWORD, c.POINTER(NOTIFYICONDATA)]
        self.kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
        self.kernel.GetModuleHandleW.restype = w.HMODULE
        self.callback = WNDPROC(self._proc)

    def run_detached(self):
        threading.Thread(target=self._run, daemon=True).start()
        if not self.ready.wait(2) or self.error:
            raise RuntimeError(self.error or 'Tray startup timed out')

    def _proc(self, hwnd, message, wp, lp):
        if message == 0x8001:
            if lp == 0x203:  # WM_LBUTTONDBLCLK
                self.commands.put('toggle')
            elif lp == 0x205:  # WM_RBUTTONUP
                self.commands.put('menu')
            return 0
        if message == getattr(self, 'taskbar_created', -1):
            with self.lock:
                self.shell.Shell_NotifyIconW(0, c.byref(self.data))
            return 0
        if message == 0x10:
            self.user.DestroyWindow(hwnd)
            return 0
        if message == 2:
            with self.lock:
                self.shell.Shell_NotifyIconW(2, c.byref(self.data))
            self.user.PostQuitMessage(0)
            return 0
        return self.user.DefWindowProcW(hwnd, message, wp, lp)

    def _run(self):
        name = 'GHubIndicatorTray' + str(id(self))
        instance = self.kernel.GetModuleHandleW(None)
        try:
            self.taskbar_created = self.user.RegisterWindowMessageW('TaskbarCreated')
            wc = WNDCLASS()
            wc.lpfnWndProc, wc.hInstance, wc.lpszClassName = self.callback, instance, name
            if not self.user.RegisterClassW(c.byref(wc)):
                raise OSError(c.get_last_error(), 'Tray class registration failed')
            self.hwnd = self.user.CreateWindowExW(0, name, name, 0, 0, 0, 0, 0,
                                                   None, None, instance, None)
            if not self.hwnd:
                raise OSError(c.get_last_error(), 'Tray window creation failed')
            self.data = NOTIFYICONDATA()
            self.data.cbSize = c.sizeof(self.data)
            self.data.hWnd, self.data.uID = self.hwnd, 1
            self.data.uFlags, self.data.uCallbackMessage = 7, 0x8001
            self.data.hIcon = self.user.LoadIconW(None, c.c_void_p(32516))
            self.data.szTip = APP_NAME
            if not self.shell.Shell_NotifyIconW(0, c.byref(self.data)):
                raise OSError('Could not add notification-area icon')
            self.ready.set()
            msg = w.MSG()
            while self.user.GetMessageW(c.byref(msg), None, 0, 0) > 0:
                self.user.TranslateMessage(c.byref(msg))
                self.user.DispatchMessageW(c.byref(msg))
        except Exception as exc:
            self.error = str(exc)
            self.ready.set()
        finally:
            self.hwnd = None
            self.user.UnregisterClassW(name, instance)

    @property
    def title(self):
        return self.data.szTip

    @title.setter
    def title(self, text):
        with self.lock:
            self.data.szTip = text[:127]
            self.data.uFlags = 7
            self.shell.Shell_NotifyIconW(1, c.byref(self.data))

    def notify(self, text, title):
        with self.lock:
            self.data.szInfo, self.data.szInfoTitle = text[:255], title[:63]
            self.data.dwInfoFlags, self.data.uFlags = 1, 0x10
            ok = self.shell.Shell_NotifyIconW(1, c.byref(self.data))
            self.data.uFlags = 7
            if not ok:
                raise OSError('Tray notification unavailable')

    def stop(self):
        if self.hwnd:
            self.user.PostMessageW(self.hwnd, 0x10, 0, 0)
