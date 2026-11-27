"""Antialiased, per-pixel-alpha glass artwork and Windows layered-window presenter."""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

SCALE = 2


class GlassRenderer:
    def __init__(self):
        self.fonts = {}
        self.font_dir = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts'

    def font(self, size, bold=False):
        key = (size, bold)
        if key not in self.fonts:
            self.fonts[key] = ImageFont.truetype(str(self.font_dir / ('segoeuib.ttf' if bold else 'segoeui.ttf')), size*SCALE)
        return self.fonts[key]

    def render(self, width, height, progress, label, detail, accent=(73, 210, 255)):
        p = max(0.0, min(1.0, progress))
        sw, sh = width*SCALE, height*SCALE
        image = Image.new('RGBA', (sw, sh))

        def box(rect):
            return tuple(round(v*SCALE) for v in rect)

        def surface(rect, radius, opacity=1.0):
            if opacity <= 0:
                return
            mask = Image.new('L', (sw, sh))
            ImageDraw.Draw(mask).rounded_rectangle(box(rect), round(radius*SCALE), fill=255)
            shadow = mask.filter(ImageFilter.GaussianBlur(2*SCALE))
            shadow = ImageChops.multiply(shadow, Image.new('L', (sw, sh), round(45*opacity)))
            dark = Image.new('RGBA', (sw, sh), (4, 9, 18, 0)); dark.putalpha(shadow)
            image.alpha_composite(dark)
            gradient = Image.linear_gradient('L').resize((sw, sh))
            # A real translucent surface; no desktop screenshots or simulated background capture.
            colors = Image.new('RGBA', (sw, sh), (16, 24, 38, 247))
            top = Image.new('RGBA', (sw, sh), (61, 79, 102, 237))
            colors = Image.composite(colors, top, gradient)
            alpha = colors.getchannel('A').point(lambda v: round(v*opacity))
            colors.putalpha(ImageChops.multiply(alpha, mask))
            image.alpha_composite(colors)
            rim = Image.new('RGBA', (sw, sh))
            draw = ImageDraw.Draw(rim)
            draw.rounded_rectangle(box(rect), round(radius*SCALE), outline=(222, 239, 255, round(100*opacity)), width=SCALE)
            inner = (rect[0]+1.3, rect[1]+1.3, rect[2]-1.3, rect[3]-1.3)
            draw.rounded_rectangle(box(inner), max(1, round((radius-1)*SCALE)), outline=(255, 255, 255, round(20*opacity)), width=SCALE)
            # A narrow reflected highlight fades naturally into the lower half.
            sheen = Image.new('RGBA', (sw, sh))
            sd = ImageDraw.Draw(sheen)
            sd.ellipse(box((rect[0]-10, rect[1]-17, rect[2]-5, rect[1]+(rect[3]-rect[1])*0.62)), fill=(205, 231, 255, round(19*opacity)))
            sheen.putalpha(ImageChops.multiply(sheen.getchannel('A'), mask))
            image.alpha_composite(sheen)
            image.alpha_composite(rim)

        def text(x, y, value, size, fill, bold=False, anchor='lt', opacity=1.0):
            overlay = Image.new('RGBA', (sw, sh))
            ImageDraw.Draw(overlay).text((round(x*SCALE), round(y*SCALE)), value,
                font=self.font(size, bold), fill=(*fill, round(255*max(0,min(1,opacity)))), anchor=anchor)
            image.alpha_composite(overlay)

        compact = (width/2-21, 2, width/2+21, 44)
        full = (4, 4, width-4, height-4)
        morph = tuple(a+(b-a)*p for a,b in zip(compact,full))
        surface(morph, 21+5*p)
        surface((1, 49, width-1, min(height-1, 67)), 9, max(0, 1-p*2.2))
        text(width/2, 23, 'G', 19, accent, True, 'mm', 1-p)
        small = label
        font = self.font(8)
        while small and font.getlength(small) > (width-14)*SCALE:
            small = small[:-2]+'…' if not small.endswith('…') else small[:-2]+'…'
        text(width/2, 57, small, 8, (239, 246, 255), anchor='mm', opacity=max(0,1-p*2.2))
        opacity = max(0, (p-0.3)/0.7)
        if opacity:
            text(22, 17, 'G', 12, accent, True, opacity=opacity)
            text(40, 19, 'HUB  /  LIVE PROFILE', 8, (190, 211, 231), True, opacity=opacity)
            text(width-29, 17, '···', 15, (220, 234, 248), anchor='mt', opacity=opacity)
            lines, line = [], ''
            title_font = self.font(17, True)
            for word in label.split():
                candidate = (line+' '+word).strip()
                if title_font.getlength(candidate) > (width-44)*SCALE and line:
                    lines.append(line); line = word
                else:
                    line = candidate
            lines.append(line)
            for index, part in enumerate(lines[:2]):
                while part and title_font.getlength(part) > (width-44)*SCALE:
                    part = part[:-2]+'…'
                text(22, 42+index*22, part, 17, (248, 251, 255), True, opacity=opacity)
            text(22, height-23, detail, 8, (181, 202, 222), opacity=opacity)
        return image.resize((width,height), Image.Resampling.LANCZOS)


class POINT(c.Structure):
    _fields_ = [('x', w.LONG), ('y', w.LONG)]


class SIZE(c.Structure):
    _fields_ = [('cx', w.LONG), ('cy', w.LONG)]


class BLEND(c.Structure):
    _fields_ = [('op', c.c_ubyte), ('flags', c.c_ubyte), ('alpha', c.c_ubyte), ('format', c.c_ubyte)]


class BITMAPINFO(c.Structure):
    _fields_ = [('size', w.DWORD), ('width', w.LONG), ('height', w.LONG),
                ('planes', w.WORD), ('bits', w.WORD), ('compression', w.DWORD),
                ('image_size', w.DWORD), ('xppm', w.LONG), ('yppm', w.LONG),
                ('used', w.DWORD), ('important', w.DWORD)]


class LayeredWindow:
    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.user = c.WinDLL('user32', use_last_error=True)
        self.gdi = c.WinDLL('gdi32', use_last_error=True)
        self.user.GetDC.argtypes = [w.HWND]; self.user.GetDC.restype = w.HDC
        self.user.ReleaseDC.argtypes = [w.HWND,w.HDC]
        self.user.GetWindowLongW.argtypes = [w.HWND,c.c_int]
        self.user.SetWindowLongW.argtypes = [w.HWND,c.c_int,w.LONG]
        self.user.SetWindowRgn.argtypes = [w.HWND,w.HRGN,w.BOOL]
        self.gdi.CreateCompatibleDC.argtypes = [w.HDC]; self.gdi.CreateCompatibleDC.restype = w.HDC
        self.gdi.CreateDIBSection.argtypes = [w.HDC,c.POINTER(BITMAPINFO),w.UINT,c.POINTER(c.c_void_p),w.HANDLE,w.DWORD]
        self.gdi.CreateDIBSection.restype = w.HBITMAP
        self.gdi.SelectObject.argtypes = [w.HDC,w.HANDLE]; self.gdi.SelectObject.restype = w.HANDLE
        self.gdi.DeleteObject.argtypes = [w.HANDLE]
        self.gdi.DeleteDC.argtypes = [w.HDC]
        self.user.UpdateLayeredWindow.argtypes = [w.HWND,w.HDC,c.POINTER(POINT),c.POINTER(SIZE),w.HDC,c.POINTER(POINT),w.DWORD,c.POINTER(BLEND),w.DWORD]
        self.user.SetWindowRgn(hwnd,None,True)
        style = self.user.GetWindowLongW(hwnd,-20)
        self.user.SetWindowLongW(hwnd,-20,style|0x80000)

    def present(self, image, x, y):
        width,height = image.size
        red,green,blue,alpha = image.split()
        premultiplied = Image.merge('RGBA', (ImageChops.multiply(red,alpha),
            ImageChops.multiply(green,alpha),ImageChops.multiply(blue,alpha),alpha))
        data = premultiplied.tobytes('raw','BGRA')
        screen = self.user.GetDC(None)
        dc = self.gdi.CreateCompatibleDC(screen)
        info = BITMAPINFO(c.sizeof(BITMAPINFO),width,-height,1,32,0,width*height*4,0,0,0,0)
        pixels = c.c_void_p()
        bitmap = self.gdi.CreateDIBSection(screen,c.byref(info),0,c.byref(pixels),None,0)
        if not bitmap:
            self.gdi.DeleteDC(dc); self.user.ReleaseDC(None,screen)
            raise c.WinError(c.get_last_error())
        old = self.gdi.SelectObject(dc,bitmap)
        try:
            c.memmove(pixels,data,len(data))
            point,size,origin,blend = POINT(x,y),SIZE(width,height),POINT(0,0),BLEND(0,0,255,1)
            if not self.user.UpdateLayeredWindow(self.hwnd,screen,c.byref(point),c.byref(size),dc,c.byref(origin),0,c.byref(blend),2):
                raise c.WinError(c.get_last_error())
        finally:
            self.gdi.SelectObject(dc,old); self.gdi.DeleteObject(bitmap)
            self.gdi.DeleteDC(dc); self.user.ReleaseDC(None,screen)
