"""Shop wording: tech-facing GD and Bay PDF output must not say channel."""
import re
import unittest
from pathlib import Path

from bay_procedure import (
    apply_shop_channel_wording,
    compile_bay_procedure,
    pdf_content_operators,
    procedure_body_text,
    procedure_plain_text,
    render_bay_procedure_pdf,
)
from gd_library_coach import (
    BAL_TONGUE_PRODUCT_LOCK,
    OPEN_LIBRARY_COACH_RULE,
    SHOP_LANGUAGE_RULE,
    WATER_HEATER_PRODUCT_LOCK,
    facr_freeze_proves_from_text,
    rewrite_shop_channel_words,
)

ROOT = Path(__file__).resolve().parents[1]
CHANNEL_RE = re.compile(r"\bchannels?\b", re.I)

BAL_WO = (
    "BAL Soft-Touch SS 5.1 electric tongue jack dead. "
    "Other stabilizers and panel lights work. Motor OK on direct 12V. Coupler OK."
)


def _pdf_text(pdf: bytes) -> str:
    try:
        import pymupdf

        doc = pymupdf.open(stream=pdf, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    except Exception:
        return pdf_content_operators(pdf)


def _without_channel_ban(text: str) -> str:
    """Drop the prompt line that names the banned jargon."""
    kept = []
    for line in (text or "").splitlines():
        low = line.lower()
        if "channel" in low and any(
            k in low for k in ("do not", "don't", "avoid", "never say", "jargon", "shop words")
        ):
            continue
        kept.append(line)
    return "\n".join(kept)


def _assert_no_channel(testcase, text, label):
    match = CHANNEL_RE.search(text or "")
    testcase.assertIsNone(
        match,
        f"{label} still says {match.group(0)!r}" if match else label,
    )


class TestShopChannelFilter(unittest.TestCase):
    def test_user_example_and_plural_and_case(self):
        raw = "Prove 12V at the soft-touch panel tongue channel while you command extend"
        out = rewrite_shop_channel_words(raw)
        self.assertIn("tongue jack output wire at the panel", out.lower())
        _assert_no_channel(self, out, "example")
        self.assertEqual(
            rewrite_shop_channel_words("The stabilizer channels are live."),
            "The stabilizer circuits are live.",
        )
        self.assertEqual(rewrite_shop_channel_words("CHANNEL"), "WIRE")
        self.assertEqual(rewrite_shop_channel_words("Channels"), "Circuits")

    def test_marked_oem_source_quote_stays_verbatim(self):
        raw = (
            "Prove 12V at the soft-touch panel tongue channel.\n"
            "📖 Source: BAL SS 5.1 Stabilizing System INS.STA.001\n"
            '"tongue channel voltage at the panel connector"'
        )
        out = rewrite_shop_channel_words(raw)
        before, _sep, quote = out.partition("📖 Source:")
        _assert_no_channel(self, before, "prose before source")
        self.assertIn("tongue channel voltage at the panel connector", quote)
        self.assertIn("20300427", rewrite_shop_channel_words("Replace panel 20300427 on that channel."))
        kept = rewrite_shop_channel_words('OEM source quote: "check the tongue channel"')
        self.assertIn("tongue channel", kept)


if __name__ == "__main__":
    unittest.main()
