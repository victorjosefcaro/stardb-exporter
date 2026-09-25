import ctypes
from ctypes import wintypes
from typing import Optional, Tuple
from PIL import Image, ImageGrab

user32 = ctypes.windll.user32
shcore = getattr(ctypes.windll, "shcore", None)

# Enable DPI Awareness so window coordinates are exact
try:
    if shcore and hasattr(shcore, "SetProcessDpiAwareness"):
        shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
    elif hasattr(user32, "SetProcessDpiAwarenessContext"):
        user32.SetProcessDpiAwarenessContext(-4) # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2
except Exception:
    pass

class WindowCapture:
    KNOWN_TITLES = ["zenlesszonezero", "zenless zone zero", "绝区零"]

    @classmethod
    def find_zzz_window(cls) -> Optional[Tuple[int, str]]:
        """Finds the Zenless Zone Zero game window HWND and title."""
        found = None

        def enum_handler(hwnd, _):
            nonlocal found
            if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title_lower = buf.value.lower()
                    for target in cls.KNOWN_TITLES:
                        if target in title_lower:
                            found = (hwnd, buf.value)
                            return False
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_handler), 0)
        return found

    @classmethod
    def capture_window(cls, hwnd: int) -> Optional[Image.Image]:
        """Capture the client area of the specified window."""
        if not user32.IsWindow(hwnd):
            return None

        # Get client rect in client coordinates (0, 0, width, height)
        client_rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(client_rect))

        # Convert top-left and bottom-right to screen coordinates
        top_left = wintypes.POINT(client_rect.left, client_rect.top)
        bottom_right = wintypes.POINT(client_rect.right, client_rect.bottom)

        user32.ClientToScreen(hwnd, ctypes.byref(top_left))
        user32.ClientToScreen(hwnd, ctypes.byref(bottom_right))

        width = bottom_right.x - top_left.x
        height = bottom_right.y - top_left.y

        if width <= 0 or height <= 0:
            return None

        bbox = (top_left.x, top_left.y, bottom_right.x, bottom_right.y)
        try:
            return ImageGrab.grab(bbox=bbox, all_screens=True)
        except Exception as e:
            print(f"[Capture] Error grabbing window: {e}")
            return None

    @classmethod
    def capture_clipboard(cls) -> Optional[Image.Image]:
        """Grab image from clipboard if available."""
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            return img
        return None

if __name__ == "__main__":
    win = WindowCapture.find_zzz_window()
    if win:
        print(f"Detected ZZZ Window: {win[1]} (HWND: {win[0]})")
        screenshot = WindowCapture.capture_window(win[0])
        if screenshot:
            print(f"Captured client area: {screenshot.size[0]}x{screenshot.size[1]}")
    else:
        print("ZZZ window not detected (start the game in windowed/borderless mode).")
