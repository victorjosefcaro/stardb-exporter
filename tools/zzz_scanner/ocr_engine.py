import io
import asyncio
from typing import List, Dict, Any
from PIL import Image
from winsdk.windows.media.ocr import OcrEngine
from winsdk.windows.graphics.imaging import BitmapDecoder
from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
from winsdk.windows.globalization import Language

class WindowsOcr:
    def __init__(self, lang_tag: str = "en-US"):
        self.lang_tag = lang_tag
        self.engine = None
        self._init_engine()

    def _init_engine(self):
        try:
            lang = Language(self.lang_tag)
            self.engine = OcrEngine.try_create_from_language(lang)
        except Exception:
            self.engine = None

        if not self.engine:
            self.engine = OcrEngine.try_create_from_user_profile_languages()

        if not self.engine:
            langs = OcrEngine.available_recognizer_languages
            if len(langs) > 0:
                self.engine = OcrEngine.try_create_from_language(langs[0])

        if not self.engine:
            raise RuntimeError("Failed to initialize Windows.Media.Ocr engine. Ensure an OCR language pack is installed.")

    async def _recognize_async(self, pil_image: Image.Image) -> List[Dict[str, Any]]:
        # Ensure RGBA mode for bitmap conversion
        if pil_image.mode != "RGBA":
            pil_image = pil_image.convert("RGBA")

        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        bytes_data = buf.getvalue()

        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(bytes_data)
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()

        result = await self.engine.recognize_async(bitmap)
        lines = []

        for line in result.lines:
            text = line.text.strip()
            if not text:
                continue

            # Calculate bounding box
            min_x = 999999
            min_y = 999999
            max_x = 0
            max_y = 0

            for word in line.words:
                r = word.bounding_rect
                min_x = min(min_x, r.x)
                min_y = min(min_y, r.y)
                max_x = max(max_x, r.x + r.width)
                max_y = max(max_y, r.y + r.height)

            lines.append({
                "text": text,
                "bbox": (min_x, min_y, max_x, max_y) if min_x < max_x else (0, 0, 0, 0),
            })

        return lines

    def recognize(self, pil_image: Image.Image) -> List[Dict[str, Any]]:
        """Synchronous wrapper to recognize text in a PIL Image."""
        return asyncio.run(self._recognize_async(pil_image))

if __name__ == "__main__":
    ocr = WindowsOcr()
    test_img = Image.new("RGBA", (300, 80), (255, 255, 255, 255))
    lines = ocr.recognize(test_img)
    print("OCR Engine test complete. Lines recognized:", len(lines))
