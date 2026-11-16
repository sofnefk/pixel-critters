"""
PIXEL CRITTERS - an interactive animated desktop background (Windows).

Run a preview in a normal window:   python critters.py
Run as your real wallpaper:         python critters.py wallpaper
Make a picture for the lock screen: python critters.py snapshot koi

Controls (work from anywhere, even in wallpaper mode):
    Ctrl+Alt+Right / Left  = next / previous animal
    Ctrl+Alt+Q             = quit
    Esc                    = quit (preview window only)
Move your mouse near the animals and they run away. Click = scatter + ripple.
"""
import ctypes
import math
import os
import random
import sys
import time
from ctypes import wintypes

import pygame

# ============================================================
#  SETTINGS - play with these!
# ============================================================
START_SPECIES = "random"   # "random" or one of: butterfly jellyfish dragonfly koi frog crab
AUTO_SWITCH_SECONDS = 45    # 0 = never switch by itself, 120 = new animal every 2 minutes
CELL = 10                  # size of one pixel-cell in real pixels (bigger = chunkier, faster)
FPS = 30
FLEE_RADIUS = 10           # in cells: how close the mouse must be to scare them
CLICK_RADIUS = 28          # in cells: how far a click reaches
CLICK_POWER = 2.0          # how hard a click pushes them
COUNT_SCALE = 1.0          # more animals (1.5) or fewer (0.6)
LABEL_FRAMES = 75          # how long the animal name shows after switching

# ============================================================
#  WINDOWS PLUMBING (talking to Windows directly)
# ============================================================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)   # real pixels on high-res screens
except Exception:
    pass

user32 = ctypes.windll.user32
ENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
user32.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM,
                                       wintypes.LPARAM, wintypes.UINT, wintypes.UINT,
                                       ctypes.c_void_p]
user32.SendMessageTimeoutW.restype = ctypes.c_void_p
user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
user32.SetParent.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.SetWindowPos.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_ubyte, wintypes.DWORD]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL
user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC
user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       ctypes.POINTER(wintypes.SIZE), wintypes.HDC,
                                       ctypes.POINTER(wintypes.POINT), wintypes.DWORD,
                                       ctypes.c_void_p, wintypes.DWORD]
user32.UpdateLayeredWindow.restype = wintypes.BOOL
gdi32 = ctypes.windll.gdi32
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
                                   ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class LayeredPresenter:
    """Hands each finished frame straight to Windows (UpdateLayeredWindow).
    This is the reliable way to show pictures in the new Windows 11 desktop layer."""

    def __init__(self, hwnd, w, h):
        self.hwnd, self.w, self.h = hwnd, w, h
        self.ok = False
        self.screen_dc = user32.GetDC(None)
        self.mem_dc = gdi32.CreateCompatibleDC(self.screen_dc)
        bmi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)  # -h = top-down
        self.bits = ctypes.c_void_p()
        self.bitmap = gdi32.CreateDIBSection(self.screen_dc, ctypes.byref(bmi), 0, ctypes.byref(self.bits), None, 0)
        if self.bitmap and self.bits.value:
            gdi32.SelectObject(self.mem_dc, self.bitmap)
            self.ok = True
        self.size = wintypes.SIZE(w, h)
        self.src = wintypes.POINT(0, 0)
        self.blend = BLENDFUNCTION(0, 0, 255, 0)      # fully visible, no per-pixel alpha

    def present(self, surface):
        if not self.ok:
            return False
        data = pygame.image.tobytes(surface, "BGRA")
        ctypes.memmove(self.bits, data, len(data))
        return bool(user32.UpdateLayeredWindow(self.hwnd, self.screen_dc, None, ctypes.byref(self.size),
                                               self.mem_dc, ctypes.byref(self.src), 0,
                                               ctypes.byref(self.blend), 2))      # 2 = ULW_ALPHA

VK_LBUTTON, VK_CONTROL, VK_ALT = 0x01, 0x11, 0x12
VK_LEFT, VK_RIGHT, VK_Q = 0x25, 0x27, 0x51


def key_down(vk):
    """True if this key / mouse button is held down anywhere in Windows."""
    return (user32.GetAsyncKeyState(vk) & 0x8000) != 0


def cursor_pos():
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def class_name(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def print_children(parent):
    """Debug: the windows inside `parent`, from top to bottom."""
    child = user32.GetWindow(parent, 5)          # GW_CHILD = the top one
    n = 0
    while child and n < 12:
        print(f"    {hex(child)}  {class_name(child)}", flush=True)
        child = user32.GetWindow(child, 2)       # GW_HWNDNEXT = the next one down
        n += 1


def make_gdi_layered(hwnd):
    """Backup way to show the window: plain layered window, drawn by pygame itself."""
    GWL_EXSTYLE, WS_EX_LAYERED = -20, 0x80000
    ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex & ~WS_EX_LAYERED)
    user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
    user32.SetLayeredWindowAttributes(hwnd, 0, 255, 2)       # 2 = use alpha, 255 = fully visible


def attach_to_desktop(hwnd, w, h):
    """Put our window BEHIND the desktop icons, so it acts as the wallpaper.
    Returns (function that re-fixes the window order, True if the layered window needs special drawing)."""
    progman = user32.FindWindowW("Progman", None)
    # secret message that makes Windows create the "WorkerW" window we hide behind
    user32.SendMessageTimeoutW(progman, 0x052C, 0, 0, 0, 1000, None)

    found = []

    def look(top, _):
        if user32.FindWindowExW(top, None, "SHELLDLL_DefView", None):
            worker = user32.FindWindowExW(None, top, "WorkerW", None)
            if worker:
                found.append(worker)
        return True

    user32.EnumWindows(ENUMPROC(look), 0)

    GWL_STYLE, GWL_EXSTYLE = -16, -20
    WS_CHILD, WS_POPUP, WS_VISIBLE, WS_EX_LAYERED = 0x40000000, 0x80000000, 0x10000000, 0x80000

    if found:      # older layout (Windows 10 / older Windows 11)
        layout, parent, insert_after = "old", found[0], 1       # 1 = bottom
    else:          # newer Windows 11 (24H2 / 25H2): everything lives inside Progman
        defview = user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None)
        layout, parent, insert_after = "new", progman, (defview or 1)
        # on the new layout our window MUST be "layered", set BEFORE parenting
        if "gdi" in sys.argv:
            make_gdi_layered(hwnd)
        else:
            ex = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
    print(f"wallpaper: windows build {sys.getwindowsversion().build}, layout={layout}, parent={hex(parent or 0)}", flush=True)

    style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    user32.SetWindowLongPtrW(hwnd, GWL_STYLE, (style & ~WS_POPUP) | WS_CHILD | WS_VISIBLE)
    user32.SetParent(hwnd, parent)

    def fix_order():
        # SWP_NOACTIVATE = 0x10, SWP_SHOWWINDOW = 0x40
        user32.SetWindowPos(hwnd, insert_after, 0, 0, w, h, 0x10 | 0x40)

    fix_order()
    user32.ShowWindow(hwnd, 5)

    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    print(f"wallpaper: our window = {hex(hwnd)}, parent ok = {user32.GetParent(hwnd) == parent}, "
          f"visible = {bool(user32.IsWindowVisible(hwnd))}, "
          f"position = ({rect.left},{rect.top})-({rect.right},{rect.bottom}), screen = {w}x{h}", flush=True)
    print("wallpaper: windows inside Progman, top to bottom:", flush=True)
    print_children(progman)
    return fix_order, (layout == "new" and "gdi" not in sys.argv)


# ============================================================
#  COLORS + PIXEL ART
#  Each animal is a little picture made of letters.
#  Every letter is a color from the animal's palette:
#     a = light   b = medium   c = dark   d = darkest
#     w = white   k = body/accent   p = pupil   '.' = empty
# ============================================================
WHITE = (240, 244, 250)


def pals(*items):
    """items = (how common, palette). Returns a list we can pick from randomly."""
    return list(items)


BUTTERFLY_PALS = pals(
    (5, dict(a=(160, 210, 255), b=(70, 145, 255), c=(40, 90, 210), d=(25, 55, 150), w=WHITE, k=(225, 240, 255))),
    (2, dict(a=(170, 255, 245), b=(60, 220, 215), c=(30, 150, 170), d=(20, 100, 130), w=WHITE, k=(225, 255, 250))),
    (1, dict(a=(225, 190, 255), b=(170, 110, 255), c=(110, 60, 200), d=(70, 40, 150), w=WHITE, k=(240, 225, 255))),
    (1, dict(a=(255, 200, 235), b=(255, 120, 200), c=(210, 70, 150), d=(150, 40, 100), w=WHITE, k=(255, 230, 245))),
)
JELLY_PALS = pals(
    (4, dict(a=(255, 205, 240), b=(235, 110, 205), c=(180, 60, 160), d=(110, 35, 110), w=WHITE)),
    (2, dict(a=(225, 195, 255), b=(165, 110, 255), c=(115, 65, 200), d=(70, 40, 140), w=WHITE)),
    (2, dict(a=(190, 245, 255), b=(90, 200, 235), c=(50, 135, 190), d=(30, 85, 130), w=WHITE)),
)
FROG_PALS = pals(
    (4, dict(a=(190, 245, 120), b=(100, 205, 60), c=(55, 140, 40), d=(30, 90, 30), w=WHITE, p=(15, 35, 15))),
    (2, dict(a=(235, 250, 130), b=(190, 225, 60), c=(130, 170, 40), d=(80, 110, 30), w=WHITE, p=(30, 40, 10))),
    (2, dict(a=(150, 245, 210), b=(60, 200, 170), c=(35, 140, 130), d=(20, 90, 90), w=WHITE, p=(10, 35, 35))),
    (1, dict(a=(255, 190, 120), b=(240, 120, 60), c=(190, 70, 40), d=(120, 40, 30), w=WHITE, p=(40, 15, 10))),
)
CRAB_PALS = pals(
    (4, dict(a=(255, 175, 145), b=(240, 100, 80), c=(190, 60, 55), d=(120, 35, 40), w=WHITE, p=(30, 10, 10))),
    (2, dict(a=(255, 215, 140), b=(250, 165, 60), c=(205, 110, 40), d=(130, 70, 30), w=WHITE, p=(40, 20, 10))),
    (1, dict(a=(255, 190, 215), b=(240, 110, 160), c=(190, 65, 115), d=(120, 40, 80), w=WHITE, p=(40, 10, 20))),
)
DRAGONFLY_PALS = pals(
    (4, dict(body=(90, 230, 120), body2=(40, 150, 80), head=(170, 255, 180), wing=(190, 240, 220), tip=(255, 90, 80))),
    (2, dict(body=(80, 200, 255), body2=(40, 120, 200), head=(170, 235, 255), wing=(200, 235, 255), tip=(255, 210, 80))),
    (2, dict(body=(255, 120, 90), body2=(190, 70, 60), head=(255, 190, 160), wing=(255, 225, 210), tip=(255, 240, 120))),
)
_R, _W, _O, _G = (225, 60, 50), (238, 238, 242), (250, 145, 55), (90, 90, 105)
_O2, _Y, _Y2 = (225, 112, 35), (255, 215, 70), (232, 178, 40)
KOI_PALS = pals(
    (4, dict(pat=[_R, _W, _R, _R, _W, _W, _R, _W, _W], fin=_W, tail=_W)),
    (3, dict(pat=[_W, _R, _W, _W, _R, _R, _W, _W, _R], fin=_W, tail=_W)),
    (2, dict(pat=[_O, _O2, _O, _O2, _O, _O2, _O, _O2, _O], fin=(255, 190, 110), tail=(255, 170, 90))),
    (2, dict(pat=[_Y, _Y2, _Y, _Y2, _Y, _Y2, _Y, _Y2, _Y], fin=(255, 235, 150), tail=(255, 225, 120))),
    (1, dict(pat=[_W, _G, _R, _W, _G, _W, _G, _W, _W], fin=_W, tail=_W)),
)

# ---- butterfly (11 x 9, flaps: open / half / closed) ----
BF_OPEN = [
    "....k.k....",
    "aab..k..baa",
    "abbb.k.bbba",
    "abwbbkbbwba",
    ".abbbkbbba.",
    "..bbbkbbb..",
    "..cbbkbbc..",
    "..dcckccd..",
    "...dd.dd...",
]
BF_MID = [
    "....k.k....",
    "..ab.k.ba..",
    "..bbbkbbb..",
    "..bwbkbwb..",
    "...bbkbb...",
    "...cbkbc...",
    "...cckcc...",
    "....dkd....",
    "....d.d....",
]
BF_CLOSED = [
    "....k.k....",
    ".....k.....",
    "....bkb....",
    "....bkb....",
    "....ckc....",
    "....ckc....",
    "....dkd....",
    ".....d.....",
    "...........",
]

# ---- jellyfish (11 x 9, faces UP, rotates toward where it swims) ----
JELLY_WIDE = [
    "...bbbbb...",
    ".bbaaaaabb.",
    "bbaawaawabb",
    "bcbbbbbbbcb",
    ".c.c.c.c.c.",
    "..c.c.c.c..",
    ".c...c...c.",
    "..d..d..d..",
    "....d.d....",
]
JELLY_NARROW = [
    "....bbb....",
    "...baaab...",
    "...bawab...",
    "...bbbbb...",
    "...c.c.c...",
    "...c.c.c...",
    "....c.c....",
    "....d.d....",
    ".....d.....",
]

# ---- frog (11 x 11, faces UP) ----
FROG_SIT = [
    ".ww.....ww.",
    ".wpbbbbbpw.",
    "..bbaaabb..",
    "bb.baaab.bb",
    "b.bbaaabb.b",
    ".bbaacaabb.",
    ".bbbaaabbb.",
    "bbbbaaabbbb",
    "bb.bbabb.bb",
    "bb..bbb..bb",
    "bbb.....bbb",
]
FROG_LEAP = [
    ".ww.....ww.",
    "bwpbbbbbpwb",
    "b.bbaaabb.b",
    "..bbaaabb..",
    "..bbaaabb..",
    "...baaab...",
    "..bb.a.bb..",
    ".bb..c..bb.",
    ".b...c...b.",
    "bb...d...bb",
    "bb.......bb",
]

# ---- crab (13 x 9, claws UP; sideways walking) ----
CRAB_A = [
    "bb.........bb",
    "bab..w.w..bab",
    ".bb.bbbbb.bb.",
    "..bbbaaabbb..",
    "c.bbaaaaabb.c",
    ".c.bbbcbbb.c.",
    "c..cbbbbbc..c",
    ".c..ccccc..c.",
    "c...........c",
]
CRAB_B = [
    "bb.........bb",
    "bab..w.w..bab",
    ".bb.bbbbb.bb.",
    "..bbbaaabbb..",
    ".c.bbaaabb.c.",
    "c..bbbcbbb..c",
    ".c.cbbbbbc.c.",
    "c..ccccccc..c",
    "...c.....c...",
]

SPRITES = {
    "butterfly": [BF_OPEN, BF_MID, BF_CLOSED],
    "jellyfish": [JELLY_WIDE, JELLY_NARROW],
    "frog": [FROG_SIT, FROG_LEAP],
    "crab": [CRAB_A, CRAB_B],
}

# ============================================================
#  HELPERS
# ============================================================
def wrap_angle(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


def rnd(v):
    return int(math.floor(v + 0.5))


_rot_cache = {}


def sprite_cells(kind, frame, idx):
    """Cells of a sprite turned by idx * 90 degrees (exact, so it stays crisp)."""
    key = (kind, frame, idx)
    if key in _rot_cache:
        return _rot_cache[key]
    rows = SPRITES[kind][frame % len(SPRITES[kind])]
    h, w = len(rows), len(rows[0])
    cx0, cy0 = (w - 1) / 2, (h - 1) / 2
    th = idx * math.pi / 4
    c, s = round(math.cos(th)), round(math.sin(th))
    R = int(math.hypot(w, h) / 2) + 1
    out = []
    for ty in range(-R, R + 1):
        for tx in range(-R, R + 1):
            ix = rnd(tx * c + ty * s + cx0)
            iy = rnd(-tx * s + ty * c + cy0)
            if 0 <= ix < w and 0 <= iy < h and rows[iy][ix] != ".":
                out.append((tx, ty, rows[iy][ix]))
    _rot_cache[key] = out
    return out


def pick(palettes):
    return random.choices([p for _, p in palettes], weights=[w for w, _ in palettes])[0]


# how many, how scared of the mouse, personal space, trail fade, trail characters, ripple color
SPECIES = {
    "butterfly": dict(count=12, skit=1.0, sep=5.0, decay=0.80, glyphs=".:'",  pals=BUTTERFLY_PALS, color=(90, 150, 255)),
    "jellyfish": dict(count=9,  skit=0.6, sep=9.0, decay=0.93, glyphs=")(|/\\", pals=JELLY_PALS,    color=(215, 90, 200)),
    "dragonfly": dict(count=8,  skit=1.5, sep=7.0, decay=0.90, glyphs="/\\|-", pals=DRAGONFLY_PALS, color=(90, 230, 120)),
    "koi":       dict(count=10, skit=1.0, sep=8.0, decay=0.80, glyphs=".:'",  pals=KOI_PALS,       color=(255, 150, 70)),
    "frog":      dict(count=9,  skit=1.2, sep=9.0, decay=0.80, glyphs=".:'",  pals=FROG_PALS,      color=(110, 220, 60)),
    "crab":      dict(count=10, skit=1.2, sep=8.0, decay=0.80, glyphs=".:'",  pals=CRAB_PALS,      color=(240, 100, 80)),
}
ORDER = list(SPECIES)

MIN_B = 0.07               # below this brightness a trail cell disappears
MAX_SPEED = 1.8
RIPPLE_MAX = 18
KOI_RADII = [1.5, 1.9, 2.0, 1.9, 1.6, 1.4, 1.2, 0.9, 0.7]
KOI_GAP = 1.35


def lighten(col, amount):
    return tuple(min(255, c + amount) for c in col)


# ============================================================
#  ONE ANIMAL
# ============================================================
class Critter:
    def __init__(self, kind, cols, rows):
        self.kind = kind
        self.cols, self.rows = cols, rows
        self.pal = pick(SPECIES[kind]["pals"])
        self.x = random.uniform(12, cols - 12)
        self.y = random.uniform(10, rows - 10)
        self.vx = self.vy = 0.0
        self.hd = random.uniform(-math.pi, math.pi)
        self.t = random.randint(0, 200)
        self.timer = random.randint(5, 80)
        self.ang = random.uniform(-math.pi, math.pi)
        self.frame = 0
        self.dir = (0, 0)          # crab walking direction
        self.orient = 0            # crab/frog: which way the picture is turned
        self.hop_t = 0             # frog: frames left in the air
        self.hop_v = (0.0, 0.0)
        self.landed = False
        self.off = random.randint(0, 43)
        if kind == "koi":
            self.seg = [[self.x - math.cos(self.hd) * KOI_GAP * i,
                         self.y - math.sin(self.hd) * KOI_GAP * i] for i in range(len(KOI_RADII))]

    def near_edge(self):
        return self.x < 14 or self.x > self.cols - 14 or self.y < 10 or self.y > self.rows - 10

    def angle_to_center(self):
        return math.atan2(self.rows / 2 - self.y, self.cols / 2 - self.x)

    # ---------------- movement ----------------
    def update(self, mx, my, clicked):
        self.t += 1
        k = self.kind
        skit = SPECIES[k]["skit"]

        dx, dy = self.x - mx, self.y - my
        dist = math.hypot(dx, dy) or 0.001
        ux, uy = dx / dist, dy / dist
        scared = dist < FLEE_RADIUS
        kicked = clicked and dist < CLICK_RADIUS

        if k not in ("frog",):             # frogs react by hopping (below)
            if scared:
                push = (1 - dist / FLEE_RADIUS) * 0.25 * skit
                self.vx += ux * push
                self.vy += uy * push
            if kicked:
                power = CLICK_POWER * (1 - 0.6 * dist / CLICK_RADIUS) * skit
                self.vx += ux * power
                self.vy += uy * power

        if k == "butterfly":
            self.vx += random.uniform(-0.09, 0.09)
            self.vy += random.uniform(-0.09, 0.09) + math.sin(self.t * 0.35) * 0.04
            friction = 0.93
            self.frame = (0, 1, 2, 1)[(self.t // 3) % 4]

        elif k == "jellyfish":
            phase = (self.t + self.off) % 44
            if scared:
                self.ang = math.atan2(uy, ux)
            if phase == 0:
                self.ang += random.uniform(-0.8, 0.8)
            if self.near_edge():
                self.ang += wrap_angle(self.angle_to_center() - self.ang) * 0.12
            if phase < 9:                  # squeeze = swim forward
                self.vx += math.cos(self.ang) * 0.10
                self.vy += math.sin(self.ang) * 0.10
            friction = 0.93
            self.frame = 1 if phase < 9 else 0

        elif k == "dragonfly":
            self.timer -= 1
            if self.timer <= 0:            # sudden dart
                a = random.uniform(0, 2 * math.pi)
                if self.near_edge():
                    a = self.angle_to_center() + random.uniform(-0.7, 0.7)
                self.vx += math.cos(a) * 1.4
                self.vy += math.sin(a) * 1.0
                self.timer = random.randint(30, 110)
            self.vx += random.uniform(-0.03, 0.03)
            self.vy += random.uniform(-0.03, 0.03)
            friction = 0.91

        elif k == "koi":
            self.timer -= 1
            if self.timer <= 0:
                self.ang += random.uniform(-0.9, 0.9)
                self.timer = random.randint(30, 90)
            if self.near_edge():
                self.ang += wrap_angle(self.angle_to_center() - self.ang) * 0.08
            self.vx += (math.cos(self.ang) * 0.33 - self.vx) * 0.08
            self.vy += (math.sin(self.ang) * 0.27 - self.vy) * 0.08
            friction = 0.97

        elif k == "frog":
            if self.hop_t > 0:             # in the air: fast and straight
                self.hop_t -= 1
                self.vx, self.vy = self.hop_v
                if self.hop_t == 0:
                    self.vx = self.vy = 0.0
                    self.landed = True
            else:
                self.timer -= 1
                self.vx = self.vy = 0.0
                if scared or kicked or self.timer <= 0:
                    a = math.atan2(uy, ux) if (scared or kicked) else random.uniform(0, 2 * math.pi)
                    if self.near_edge() and not (scared or kicked):
                        a = self.angle_to_center() + random.uniform(-0.8, 0.8)
                    speed = 2.0 if kicked else 1.5
                    self.hop_v = (math.cos(a) * speed, math.sin(a) * speed)
                    self.hop_t = 8 if kicked else 6
                    self.timer = random.randint(25, 90)
                    self.hd = a
                    # which of the 4 directions is closest?
                    self.orient = (round((a + math.pi / 2) / (math.pi / 2)) % 4) * 2
            friction = 1.0
            self.frame = 1 if self.hop_t > 0 else 0

        else:  # crab: walks sideways, in all four directions
            self.timer -= 1
            if scared:
                self.dir = (1 if ux > 0 else -1, 0) if abs(ux) > abs(uy) else (0, 1 if uy > 0 else -1)
                self.timer = 40
            elif self.timer <= 0:
                self.dir = random.choice([(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0), (-1, 0), (1, 0)])
                self.timer = random.randint(25, 90)
            if self.near_edge():           # turn around at the edge
                if self.x < 14: self.dir = (1, 0)
                elif self.x > self.cols - 14: self.dir = (-1, 0)
                elif self.y < 10: self.dir = (0, 1)
                elif self.y > self.rows - 10: self.dir = (0, -1)
            self.vx += self.dir[0] * 0.07
            self.vy += self.dir[1] * 0.07
            if self.dir[1] != 0:
                self.orient = 2
            elif self.dir[0] != 0:
                self.orient = 0
            friction = 0.86
            moving = abs(self.vx) + abs(self.vy) > 0.12
            self.frame = (self.t // 5) % 2 if moving else 0

        # --- physics ---
        self.vx *= friction
        self.vy *= friction
        speed = math.hypot(self.vx, self.vy)
        if speed > MAX_SPEED:
            self.vx *= MAX_SPEED / speed
            self.vy *= MAX_SPEED / speed
            speed = MAX_SPEED
        self.x += self.vx
        self.y += self.vy
        if k in ("koi", "dragonfly", "butterfly") and speed > 0.07:
            self.hd += wrap_angle(math.atan2(self.vy, self.vx) - self.hd) * 0.18

        # --- screen edges (everyone stays on screen) ---
        if self.y < 6:
            self.y, self.vy = 6, abs(self.vy)
        elif self.y > self.rows - 6:
            self.y, self.vy = self.rows - 6, -abs(self.vy)
        if self.x < 8:
            self.x, self.vx = 8, abs(self.vx)
        elif self.x > self.cols - 8:
            self.x, self.vx = self.cols - 8, -abs(self.vx)

        if k == "koi":                     # body segments follow the head
            self.seg[0] = [self.x, self.y]
            for i in range(1, len(self.seg)):
                px, py = self.seg[i - 1]
                sx, sy = self.seg[i]
                d = math.hypot(sx - px, sy - py) or 0.001
                self.seg[i] = [px + (sx - px) / d * KOI_GAP, py + (sy - py) / d * KOI_GAP]

    # ---------------- drawing ----------------
    def render(self, w):
        if self.kind == "koi":
            self.render_koi(w)
        elif self.kind == "dragonfly":
            self.render_dragonfly(w)
        else:
            idx = self.orient if self.kind in ("frog", "crab") else 0
            cx, cy = rnd(self.x), rnd(self.y)
            for dx, dy, ch in sprite_cells(self.kind, self.frame, idx):
                w.stamp(cx + dx, cy + dy, self.pal[ch])

    def render_koi(self, w):
        pat = self.pal["pat"]
        nx, ny = -math.sin(self.hd), math.cos(self.hd)
        pts = []
        for i, (x, y) in enumerate(self.seg):
            off = math.sin(self.t * 0.28 - i * 0.7) * (0.12 + 0.1 * i)
            pts.append((x + nx * off, y + ny * off))
        # tail fin
        tx, ty = pts[-1]
        bx, by = pts[-2]
        d = math.hypot(tx - bx, ty - by) or 1
        fx, fy = (tx - bx) / d, (ty - by) / d
        flick = math.sin(self.t * 0.28 - 9 * 0.7)
        for k_, sp in ((1, 0.0), (2, 1.0), (3, 1.4)):
            for side in ((-1, 1) if sp else (0,)):
                w.stamp(rnd(tx + fx * k_ + nx * (side * sp + flick * 0.5)),
                        rnd(ty + fy * k_ + ny * (side * sp + flick * 0.5)), self.pal["tail"])
        # side fins
        px, py = pts[2]
        for side in (-1, 1):
            w.stamp(rnd(px + nx * side * 2.2), rnd(py + ny * side * 2.2 + 0.5), self.pal["fin"])
            w.stamp(rnd(px + nx * side * 2.7 - fx * 1), rnd(py + ny * side * 2.7 - fy * 1), self.pal["fin"])
        # body, tail first so the head ends up on top
        for i in range(len(pts) - 1, -1, -1):
            x, y = pts[i]
            r = KOI_RADII[i]
            col = pat[i]
            for cy in range(int(y - r) - 1, int(y + r) + 2):
                for cx in range(int(x - r) - 1, int(x + r) + 2):
                    ddx, ddy = cx - x, cy - y
                    if ddx * ddx + ddy * ddy <= r * r + 0.25:
                        shade = lighten(col, 18) if ddx + ddy < -r * 0.5 else col
                        w.stamp(cx, cy, shade)
        hx, hy = pts[0]
        fwd = (math.cos(self.hd), math.sin(self.hd))
        for side in (-1, 1):
            w.stamp(rnd(hx + fwd[0] * 0.6 + nx * side * 0.9), rnd(hy + fwd[1] * 0.6 + ny * side * 0.9), (25, 25, 35))

    def render_dragonfly(self, w):
        p = self.pal
        a = self.hd
        ca, sa = math.cos(a), math.sin(a)
        nx, ny = -sa, ca
        hx, hy = self.x, self.y
        flap = (self.t // 2) % 2
        tx, ty = hx - ca * 1.5, hy - sa * 1.5          # where the wings attach
        for wa in ((0.9 if flap else 1.35), -(0.9 if flap else 1.35),
                   (1.95 if flap else 1.65), -(1.95 if flap else 1.65)):
            for k_ in range(1, 6):
                col = p["wing"] if k_ < 4 else tuple(int(c * 0.6) for c in p["wing"])
                w.stamp(rnd(tx + math.cos(a + wa) * k_), rnd(ty + math.sin(a + wa) * k_), col)
        L = 11
        for i in range(2 * L, 0, -1):                   # long thin body, tail first
            t = i / 2
            col = p["tip"] if i >= 2 * L - 1 else (p["body"] if int(t) % 3 else p["body2"])
            w.stamp(rnd(hx - ca * t), rnd(hy - sa * t), col)
        for ddx, ddy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            w.stamp(rnd(hx) + ddx, rnd(hy) + ddy, p["head"])
        for side in (-1, 1):
            w.stamp(rnd(hx + ca * 0.8 + nx * side * 1.5), rnd(hy + sa * 0.8 + ny * side * 1.5), WHITE)


# ============================================================
#  THE WORLD (all animals of the current species + trails)
# ============================================================
class World:
    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        start = START_SPECIES if START_SPECIES in SPECIES else random.choice(ORDER)
        self.set_species(start)

    def set_species(self, name):
        self.kind = name
        self.cells = {}        # (cx, cy) -> [brightness, color]
        self.ripples = []      # [cx, cy, radius, max radius]
        n = max(1, int(SPECIES[name]["count"] * COUNT_SCALE))
        self.critters = [Critter(name, self.cols, self.rows) for _ in range(n)]
        self.label_left = LABEL_FRAMES
        self.switched_at = time.time()

    def change_species(self, step):
        i = (ORDER.index(self.kind) + step) % len(ORDER)
        self.set_species(ORDER[i])

    def stamp(self, cx, cy, color):
        if 0 <= cx < self.cols and 0 <= cy < self.rows:
            self.cells[(cx, cy)] = [1.0, color]

    def glow(self, cx, cy, value, color):
        if 0 <= cx < self.cols and 0 <= cy < self.rows:
            cur = self.cells.get((cx, cy))
            if cur is None or cur[0] < value:
                self.cells[(cx, cy)] = [value, color]

    def keep_apart(self):
        sep = SPECIES[self.kind]["sep"]
        cs = self.critters
        for i in range(len(cs)):
            a = cs[i]
            for j in range(i + 1, len(cs)):
                b = cs[j]
                dx, dy = a.x - b.x, a.y - b.y
                d = math.hypot(dx, dy)
                if 0 < d < sep:
                    f = (1 - d / sep) * 0.05
                    a.vx += dx / d * f
                    a.vy += dy / d * f
                    b.vx -= dx / d * f
                    b.vy -= dy / d * f

    def update(self, mx, my, clicked):
        info = SPECIES[self.kind]
        if clicked:
            self.ripples.append([mx, my, 0.0, RIPPLE_MAX])

        decay = info["decay"]
        self.cells = {k: [v[0] * decay, v[1]] for k, v in self.cells.items() if v[0] * decay >= MIN_B}

        self.keep_apart()
        for c in self.critters:
            c.update(mx, my, clicked)
            c.render(self)
            if c.landed:                   # frog landed: little splash
                c.landed = False
                self.ripples.append([c.x, c.y, 2.0, 7])

        for r in self.ripples:
            r[2] += 0.9
            n = max(8, int(2 * math.pi * r[2] * 1.2))
            value = 0.1 + 0.55 * (1 - r[2] / r[3])
            for s in range(n):
                a = 2 * math.pi * s / n
                self.glow(rnd(r[0] + math.cos(a) * r[2]), rnd(r[1] + math.sin(a) * r[2]), value, info["color"])
        self.ripples = [r for r in self.ripples if r[2] < r[3]]

        if self.label_left > 0:
            self.label_left -= 1


# ============================================================
#  DRAWING TO THE SCREEN
# ============================================================
def make_background(w, h, cols, rows):
    """Black screen with a very faint dotted grid."""
    bg = pygame.Surface((w, h))
    bg.fill((0, 0, 0))
    for cy in range(rows):
        for cx in range(cols):
            bg.set_at((cx * CELL + CELL // 2, cy * CELL + CELL // 2), (26, 26, 32))
    return bg


def draw(screen, bg, world, font, cache, label_font):
    screen.blit(bg, (0, 0))
    chars = SPECIES[world.kind]["glyphs"]
    for (cx, cy), (b, color) in world.cells.items():
        x, y = cx * CELL, cy * CELL
        if b >= 0.999:                                  # solid pixel
            pygame.draw.rect(screen, color, (x + 1, y + 1, CELL - 2, CELL - 2))
        else:                                           # fading ASCII trail
            level = 1 + int(b * 4)                      # 1..4
            ch = chars[(cx * 31 + cy * 17) % len(chars)]
            key = (ch, level, color)
            g = cache.get(key)
            if g is None:
                f = 0.15 + 0.2 * level
                g = font.render(ch, True, tuple(int(c * f) for c in color))
                cache[key] = g
            screen.blit(g, (x + (CELL - g.get_width()) // 2, y + (CELL - g.get_height()) // 2))

    if world.label_left > 0:
        fade = world.label_left / LABEL_FRAMES
        col = tuple(int(c * fade) for c in (210, 210, 220))
        text = label_font.render(world.kind, True, col)
        screen.blit(text, ((screen.get_width() - text.get_width()) // 2, 28))


# ============================================================
#  MAIN
# ============================================================
def snapshot():
    """Saves one still picture (for the lock screen). Usage: snapshot [animal name]"""
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    cols, rows = w // CELL, h // CELL
    pygame.init()
    names = [a for a in sys.argv if a in SPECIES]
    world = World(cols, rows)
    if names:
        world.set_species(names[0])
    screen = pygame.Surface((w, h))
    bg = make_background(w, h, cols, rows)
    font = pygame.font.SysFont("consolas", CELL + 2)
    label_font = pygame.font.SysFont("consolas", 22, bold=True)
    for _ in range(160):                       # let the animals spread out and leave trails
        world.update(-999, -999, False)         # mouse far away so nobody runs
    world.label_left = 0                        # no name label on the picture
    draw(screen, bg, world, font, {}, label_font)
    folder = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(folder, f"lockscreen_{world.kind}.png")
    pygame.image.save(screen, path)
    print("saved:", path, flush=True)
    pygame.quit()


def main():
    if "snapshot" in sys.argv:
        snapshot()
        return
    wallpaper = "wallpaper" in sys.argv
    print("pixel critters v5 starting,", "wallpaper mode" if wallpaper else "preview mode", flush=True)
    w = user32.GetSystemMetrics(0)
    h = user32.GetSystemMetrics(1)
    cols, rows = w // CELL, h // CELL

    os.environ["SDL_VIDEO_WINDOW_POS"] = "0,0"
    pygame.init()
    screen = pygame.display.set_mode((w, h), pygame.NOFRAME)
    pygame.display.set_caption("pixel critters")
    fix_order = presenter = None
    if wallpaper:
        hwnd = pygame.display.get_wm_info().get("window")
        if hwnd:
            fix_order, needs_presenter = attach_to_desktop(hwnd, w, h)
            if needs_presenter:
                presenter = LayeredPresenter(hwnd, w, h)
                screen.fill((0, 40, 0))                     # first test frame
                if presenter.present(screen):
                    print("wallpaper: frames are delivered to the desktop (method: UpdateLayeredWindow)", flush=True)
                else:
                    print(f"wallpaper: first drawing method not supported here (code {ctypes.GetLastError()}), "
                          f"this is normal, using the backup method", flush=True)
                    make_gdi_layered(hwnd)
                    presenter = None
        else:
            print("wallpaper: could not get the window handle, running as a normal window")

    glyph_font = pygame.font.SysFont("consolas", CELL + 2)
    label_font = pygame.font.SysFont("consolas", 22, bold=True)
    bg = make_background(w, h, cols, rows)
    world = World(cols, rows)
    cache = {}
    clock = pygame.time.Clock()

    prev_click = prev_next = prev_prev = False
    frame_no = 0
    running = True
    while running:
        frame_no += 1
        if fix_order and frame_no % 150 == 0:      # Windows sometimes shuffles windows, so re-fix
            fix_order()
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE and not wallpaper:
                running = False

        combo = key_down(VK_CONTROL) and key_down(VK_ALT)
        if combo and key_down(VK_Q):
            break

        go_next = combo and key_down(VK_RIGHT)
        go_prev = combo and key_down(VK_LEFT)
        if go_next and not prev_next:
            world.change_species(1)
        if go_prev and not prev_prev:
            world.change_species(-1)
        prev_next, prev_prev = go_next, go_prev

        if AUTO_SWITCH_SECONDS and time.time() - world.switched_at > AUTO_SWITCH_SECONDS:
            world.change_species(1)

        down = key_down(VK_LBUTTON)
        clicked = down and not prev_click
        prev_click = down

        px, py = cursor_pos()
        world.update(px / CELL, py / CELL, clicked)

        draw(screen, bg, world, glyph_font, cache, label_font)
        if presenter:
            presenter.present(screen)
        else:
            pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()