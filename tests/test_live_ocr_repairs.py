"""v4.19.58: live-library OCR and figure repairs (generic, code only)."""
import io

from PIL import Image, ImageDraw

import library_figure_backfill as fb
import manual_figures as mf




def _crop_with_caption() -> bytes:
    image = Image.new("RGB", (200, 260), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 5, 195, 200), outline="black", width=3)
    draw.text((10, 225), "FIGURE 3 - WATER", fill="black")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()










