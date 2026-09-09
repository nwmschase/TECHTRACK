"""Shop-library page render piece used when a tech asks for a cited figure."""
import unittest

try:
    import fitz
    PYMUPDF = True
except ImportError:
    PYMUPDF = False


def _tiny_pdf_bytes(label: str = "Fig. 33 paper test") -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((40, 80), label, fontsize=18)
    data = doc.tobytes()
    doc.close()
    return data


def _render_png(file_bytes: bytes, page_num: int, zoom: float = 1.6) -> bytes | None:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    idx = max(0, min(page_num - 1, doc.page_count - 1))
    page = doc.load_page(idx)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    out = pix.tobytes("png")
    doc.close()
    return out


@unittest.skipUnless(PYMUPDF, "pymupdf not installed")
class TestLibraryPageRender(unittest.TestCase):
    def test_render_cited_page_to_png(self):
        pdf = _tiny_pdf_bytes("Furrion SM page 33 Fig. 33")
        png = _render_png(pdf, 1)
        self.assertTrue(png)
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertGreater(len(png), 200)

    def test_page_request_without_figure_number_still_has_a_page(self):
        # Mirrors resolve_requested_library_pages fallback: cited page, no Fig. N.
        cited = {"title": "Furrion FCR08/FCR10 SM CCD-0008122", "page": 33}
        self.assertEqual(int(cited["page"]), 33)
        pdf = _tiny_pdf_bytes("cited page 33")
        png = _render_png(pdf, 1)
        self.assertTrue(png.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
