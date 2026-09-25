import ctypes
from ctypes import wintypes
import time
from typing import Optional, Tuple
from PIL import Image, ImageChops, ImageStat

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800
VK_ESCAPE = 0x1B
SW_RESTORE = 9

class InputController:
    @staticmethod
    def is_escape_pressed() -> bool:
        """Returns True if the user pressed the Escape key."""
        return (user32.GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0

    @staticmethod
    def scroll(clicks: int):
        """
        Scrolls mouse wheel.
        clicks < 0: scroll DOWN (e.g. -3)
        clicks > 0: scroll UP (e.g. +3)
        """
        user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, clicks * 120, 0)

    @staticmethod
    def move_to(x: int, y: int):
        """Moves cursor to screen coordinates (x, y)."""
        user32.SetCursorPos(int(x), int(y))

    @staticmethod
    def click(x: int, y: int):
        """Clicks at screen coordinates (x, y)."""
        user32.SetCursorPos(int(x), int(y))
        time.sleep(0.04)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    @staticmethod
    def is_frame_identical(img1: Image.Image, img2: Image.Image, threshold: float = 2.0) -> bool:
        """
        Calculates pixel difference between two frames.
        Returns True if difference is less than threshold (i.e. screen didn't scroll).
        """
        if img1 is None or img2 is None:
            return False
        if img1.size != img2.size or img1.mode != img2.mode:
            return False

        diff = ImageChops.difference(img1, img2)
        stat = ImageStat.Stat(diff)
        diff_avg = sum(stat.sum) / (img1.size[0] * img1.size[1])
        return diff_avg < threshold

class WindowController:
    @staticmethod
    def focus_window(hwnd: int):
        """Brings the game window reliably into the foreground."""
        if not user32.IsWindow(hwnd):
            return

        cur_thread = kernel32.GetCurrentThreadId()
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)

        if cur_thread != target_thread:
            user32.AttachThreadInput(cur_thread, target_thread, True)

        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)

        if cur_thread != target_thread:
            user32.AttachThreadInput(cur_thread, target_thread, False)

    @staticmethod
    def get_client_geometry(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
        """Returns (screen_left, screen_top, width, height) of the client area."""
        if not user32.IsWindow(hwnd):
            return None

        client_rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(client_rect))

        top_left = wintypes.POINT(client_rect.left, client_rect.top)
        bottom_right = wintypes.POINT(client_rect.right, client_rect.bottom)

        user32.ClientToScreen(hwnd, ctypes.byref(top_left))
        user32.ClientToScreen(hwnd, ctypes.byref(bottom_right))

        width = bottom_right.x - top_left.x
        height = bottom_right.y - top_left.y

        if width <= 0 or height <= 0:
            return None

        return (top_left.x, top_left.y, width, height)
