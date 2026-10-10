"""Section nav and GD send stay in session state.

Source checks do not import rv_techtrack. The AppTest below runs the script
the way Streamlit does (set_page_config and all) and signs in as the seeded
manager.
"""
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "rv_techtrack.py"


class TestGdNavAndSend(unittest.TestCase):
    def test_section_choice_is_a_keyed_radio_and_inactive_panels_do_not_render(self):
        src = APP.read_text(encoding="utf-8")
        self.assertIn('key="tt_nav"', src)
        self.assertIn("with tab_ask:", src)
        self.assertIn('"💬 Guided Diagnostics"', src)
        self.assertIn('"🧾 Bay procedure PDF"', src)
        self.assertNotIn("st.tabs(", src)
        self.assertIn("_enter_panel(tab_ask)", src)
        self.assertIn("_enter_panel(tab_dash)", src)
        self.assertIn("gd_category_memory", src)
        self.assertIn("gd_model_memory", src)

    def test_ctrl_enter_submits_the_gd_form(self):
        src = APP.read_text(encoding="utf-8")
        self.assertIn('st.form("gd_send_form"', src)
        self.assertIn("Ctrl+Enter sends this message.", src)
        self.assertIn('st.form_submit_button("Send"', src)
        # The old bare button committed the text area on Ctrl+Enter without sending.
        self.assertNotIn('st.button("Send", type="primary", key="ask_send"', src)

    def test_r2_and_cookie_cannot_hold_the_run_open(self):
        src = APP.read_text(encoding="utf-8")
        self.assertIn("connect_timeout=10", src)
        self.assertIn("read_timeout=45", src)
        self.assertIn('retries={"max_attempts": 2, "mode": "standard"}', src)
        self.assertIn(
            '_cookie_mgr = _cookie_manager() if st.session_state.user is None else None',
            src,
        )


class TestGdNavSurvivesSend(unittest.TestCase):
    """The failure on main: st.tabs plus st.rerun() jumped back to My Dashboard."""

    def test_two_sends_keep_section_category_and_model(self):
        at = AppTest.from_file(str(APP), default_timeout=60)
        at.run()
        at.text_input[0].set_value("manager")
        at.text_input[1].set_value("manager123")
        at.button[0].click().run()
        self.assertFalse(list(at.exception))

        gd = "💬 Guided Diagnostics"
        at.radio[0].set_value(gd).run()
        self.assertEqual([s.value for s in at.subheader], [gd])
        self.assertFalse(any("My Certificates" in (m.value or "") for m in at.markdown))

        at.selectbox(key="ask_cat").set_value("Refrigerators")
        at.text_input(key="ask_model").set_value("FCR10DCGTA")
        at.text_area(key="ask_input").set_value("FCR10 not cooling, cavity light is on")
        at.button(key="FormSubmitter:gd_send_form-Send").click().run()

        self.assertFalse(list(at.exception))
        self.assertEqual(at.radio[0].value, gd)
        self.assertEqual(at.selectbox(key="ask_cat").value, "Refrigerators")
        self.assertEqual(at.text_input(key="ask_model").value, "FCR10DCGTA")
        self.assertEqual(at.text_area(key="ask_input").value, "")
        self.assertEqual(at.session_state["gd_category_memory"], "Refrigerators")
        self.assertEqual(at.session_state["gd_model_memory"], "FCR10DCGTA")
        self.assertEqual(at.session_state["tt_nav"], gd)
        joined = "\n".join(m.value or "" for m in at.markdown)
        self.assertIn("FCR10 not cooling", joined)
        self.assertIn("AI is offline", joined)

        at.radio[0].set_value("📱 My Dashboard").run()
        self.assertEqual([s.value for s in at.subheader], ["📱 My Dashboard"])
        self.assertFalse(any(s.value == gd for s in at.subheader))

        at.radio[0].set_value(gd).run()
        self.assertEqual(at.selectbox(key="ask_cat").value, "Refrigerators")
        self.assertEqual(at.text_input(key="ask_model").value, "FCR10DCGTA")

        at.text_area(key="ask_input").set_value("still not cooling")
        at.button(key="FormSubmitter:gd_send_form-Send").click().run()
        self.assertEqual(at.radio[0].value, gd)
        self.assertEqual(at.selectbox(key="ask_cat").value, "Refrigerators")
        self.assertEqual(at.text_input(key="ask_model").value, "FCR10DCGTA")
        self.assertFalse(any("My Certificates" in (m.value or "") for m in at.markdown))

    def test_start_new_chat_clears_the_model_field(self):
        at = AppTest.from_file(str(APP), default_timeout=60)
        at.run()
        at.text_input[0].set_value("manager")
        at.text_input[1].set_value("manager123")
        at.button[0].click().run()
        gd = "💬 Guided Diagnostics"
        at.radio[0].set_value(gd).run()
        at.selectbox(key="ask_cat").set_value("Refrigerators")
        at.text_input(key="ask_model").set_value("FCR10DCGTA")
        at.button(key="ask_new").click().run()
        self.assertFalse(list(at.exception))
        self.assertEqual(at.text_input(key="ask_model").value, "")
        self.assertEqual(at.session_state["gd_model_memory"], "")
        self.assertEqual(at.selectbox(key="ask_cat").value, "Refrigerators")


if __name__ == "__main__":
    unittest.main()
