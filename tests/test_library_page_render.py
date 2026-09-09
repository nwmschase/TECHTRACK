"""Smoke test for the shop-library PDF page renderer used on figure asks.

Does not import rv_techtrack (Streamlit set_page_config). Matches render_pdf_page_png.
"""
import unittest

try:
    import fitz  # pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


def _render_pdf_page_png(file_bytes: bytes, page_num: int, zoom: float = 1.6):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    idx = max(0, min(page_num - 1, doc.page_count - 1))
    page = doc.load_page(idx)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return pix.tobytes("png")


@unittest.skipUnless(PYMUPDF_AVAILABLE, "pymupdf not installed")
class TestLibraryPageRender(unittest.TestCase):
    def test_render_pdf_page_png_roundtrip(self):
        doc = fitz.open()
        page = doc.new_page(width=400, height=300)
        page.insert_text((40, 80), "Shop Document Library page")
        pdf_bytes = doc.tobytes()
        doc.close()
        png = _render_pdf_page_png(pdf_bytes, 1, zoom=1.2)
        self.assertIsNotNone(png)
        self.assertGreater(len(png), 80)
        self.assertTrue(png.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
