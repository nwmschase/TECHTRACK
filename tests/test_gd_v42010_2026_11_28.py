"""v4.20.10 (Chase 2026-11-28 t1732u): the request Grok gets is ordered for xAI's prompt cache. Offline: scripted fakes,
no network, no paid call.

Same text as before, only reordered: [primer, pages read, history..., new message, rest of the job context], then within a
turn only appends (tool calls, results, page images), the REPLY FORMAT reminder last of each call and never stored."""
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import cache_share_estimate  # noqa: E402
import gd_llm  # noqa: E402
import gd_prompt  # noqa: E402
import gd_turn  # noqa: E402
from gd_fixtures import StubPageFinder  # noqa: E402
from test_fresh_core import FakeRespond, MAN, block, page  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 40


def pic(sheet):
    p = page(sheet=sheet, text=f"figure page {sheet} wiring")
    p.topics = "diagram / drawing / illustration / picture / pic / image / figure: wiring diagram"
    return p


def finder():
    return StubPageFinder(manuals=MAN, pages=[page(sheet=10 + i, text=f"plain text page {i}") for i in range(3)] + [pic(20), pic(21)])


REMINDER = gd_prompt.reminder_item()


def body(items):
    """The request without its trailing reminder."""
    assert items[-1] == REMINDER, "the reminder must be the last item of every call"
    return items[:-1]


def common(a, b):
    n = 0
    for x, y in zip(a, b):
        if json.dumps(x, sort_keys=True) != json.dumps(y, sort_keys=True):
            break
        n += 1
    return n


class Job:
    """A four-turn job: turn 1 reads a picture page, turn 2 reads nothing, turn 3 reads another picture page, turn 4 nothing."""
    SCRIPTS = [
        [[("read_pages", {"doc_id": "L1", "pages": ["20"]})], "step one " + block(summary="s1")],
        ["step two " + block(summary="s2")],
        [[("read_pages", {"doc_id": "L1", "pages": ["21"]})], "step three " + block(summary="s3")],
        ["step four " + block(summary="s4")],
    ]

    def __init__(self):
        self.store, self.history, self.f = {}, [], finder()
        self.turns = []          # per turn: the list of requests (items incl. reminder)
        self.results = []

    def run(self):
        for n, script in enumerate(self.SCRIPTS, 1):
            chat = FakeRespond(script)
            r = gd_turn.run_turn(f"tech message {n}", "Refrigerators", "Acme X1", list(self.history), finder=self.f,
                                 respond_fn=chat, store=self.store, log_path="", page_image_fn=lambda d, s: PNG)
            self.turns.append([it for it, _tools, _tc in chat.seen])
            self.results.append(r)
            self.history += [{"role": "user", "content": f"tech message {n}"}, {"role": "assistant", "content": r["reply"]}]
        return self


class TestRequestOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.job = Job().run()

    def test_old_builder_is_gone(self):
        self.assertFalse(hasattr(gd_prompt, "build_messages"))
        self.assertTrue(callable(gd_prompt.build_input))

    def test_reminder_is_last_every_call_and_never_inside_earlier_items(self):
        for reqs in self.job.turns:
            for items in reqs:
                self.assertEqual(items[-1], REMINDER)
                self.assertNotIn(REMINDER, items[:-1])

    def test_each_round_extends_the_previous_round_byte_for_byte(self):
        multi = [reqs for reqs in self.job.turns if len(reqs) > 1]
        self.assertEqual(len(multi), 2)          # turns 1 and 3 have a tool round
        for reqs in multi:
            for a, b in zip(reqs, reqs[1:]):
                a, b = body(a), body(b)
                self.assertGreater(len(b), len(a))
                self.assertEqual(common(a, b), len(a), "a later round must start with the whole earlier round")
                self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b[:len(a)], sort_keys=True))

    def test_page_images_stay_in_place_in_later_rounds(self):
        for t in (0, 2):
            r1, r2 = body(self.job.turns[t][0]), body(self.job.turns[t][1])
            self.assertEqual(len(r2) - len(r1), 3)       # the model's call, its result, the page-image message
            img = r2[-1]
            self.assertEqual(img["role"], "user")
            self.assertTrue(any(c.get("type") == "input_image" for c in img["content"]))

    def test_turn_to_turn_prefix(self):
        t = [body(reqs[0]) for reqs in self.job.turns]
        # turn 1 -> 2: the first page read puts the pages block in front of the history: only the primer is shared (once per job)
        self.assertEqual(common(t[0], t[1]), 1)
        # turn 2 -> 3: turn 2 read nothing, so turn 3 starts with ALL of turn 2's request up to and including its message
        # (primer, pages, turn 1 pair, turn 2 message); the context after it differs
        self.assertEqual(t[1][-1]["role"], "system")
        self.assertEqual(common(t[1], t[2]), len(t[1]) - 1)
        self.assertEqual(t[2][len(t[1]) - 2], {"role": "user", "content": "tech message 2"})
        # turn 3 -> 4: turn 3 read a new page, so the pages block grew: shared is the primer only
        self.assertEqual(common(t[2], t[3]), 1)
        # turn 4 vs turn 3's LAST round: still the primer only (the pages block is longer)
        # and a turn with no new page keeps the whole earlier turn as its prefix, round 1 of turn 4 vs round 1 of turn 4's own history
        self.assertEqual(t[3][1]["content"].count("=== PAGES READ EARLIER IN THIS JOB ==="), 1)

    def test_pages_block_is_append_only_in_first_read_order(self):
        p3 = self.job.turns[2][0][1]["content"]       # turn 3 round 1 = pages read in turns 1-2
        p4 = self.job.turns[3][0][1]["content"]       # turn 4 = plus the page read in turn 3
        self.assertTrue(p4.startswith(p3), "the pages block only grows at its end")
        self.assertGreater(len(p4), len(p3))

    def test_rereading_a_page_does_not_move_it(self):
        case = {"read": {}, "read_order": []}
        a, b = page(sheet=20, text="a"), page(sheet=21, text="b")
        gd_turn._remember_pages(case, [a, b])
        gd_turn._remember_pages(case, [a])
        self.assertEqual(case["read_order"], [gd_turn._key(a), gd_turn._key(b)])
        self.assertEqual([p.sheet for p in gd_turn._read_pages(case)], [20, 21])

    def test_same_text_as_the_old_order(self):
        """The old builder put one context block (unit, notes, pages, web, lookups, state, summary) after the primer; the new one
        splits it into a pages item and the rest. Same paragraphs, same messages, same history."""
        pages = [page(sheet=20, text="x"), page(sheet=21, text="y")]
        hist = [{"role": "user", "content": "u0"}, {"role": "assistant", "content": "a0"}]
        kw = dict(category="Refrigerators", model_text="Acme X1", web_sources=[{"url": "https://a.example/m.pdf"}],
                  searches=[{"tool": "search_pages", "args": '{"words": "E2"}'}], state={"cause": "c", "summary": "sum"},
                  notes=["a note"])
        new = gd_prompt.build_input(user_msg="now", history=hist, pages=pages, **kw)
        old_ctx = gd_prompt.context_block(pages=pages, **kw)
        old = ([{"role": "system", "content": gd_prompt.SYSTEM}, {"role": "system", "content": old_ctx}]
               + hist + [{"role": "user", "content": "now"}])
        self.assertEqual(new[0], old[0])
        self.assertEqual(new[2:-1], old[2:])                        # history and the new message, unchanged
        self.assertEqual(sorted((new[1]["content"] + "\n\n" + new[-1]["content"]).split("\n\n")), sorted(old_ctx.split("\n\n")))
        self.assertEqual([m["role"] for m in new], ["system", "system", "user", "assistant", "user", "system"])
        # nothing read yet: no pages item at all
        none = gd_prompt.build_input(user_msg="now", history=[], pages=[], **kw)
        self.assertEqual([m["role"] for m in none], ["system", "user", "system"])
        self.assertEqual(none[-1]["content"], gd_prompt.context_block(pages=[], **kw))

    def test_what_grok_sees_is_the_same_set_on_every_turn(self):
        """Every request holds the primer, every earlier tech message and reply, the new message and the state block, once."""
        for n, reqs in enumerate(self.job.turns, 1):
            items = body(reqs[0])
            texts = [i["content"] for i in items if isinstance(i.get("content"), str)]
            self.assertEqual(texts[0], gd_prompt.SYSTEM)
            self.assertEqual(sum(1 for x in texts if x.startswith("UNIT (as the tech typed it)")), 1)
            self.assertEqual(sum(1 for x in texts if x == f"tech message {n}"), 1)
            for k in range(1, n):
                self.assertEqual(sum(1 for x in texts if x == f"tech message {k}"), 1)
            self.assertEqual(items[-1]["role"], "system")
            self.assertIn("CASE STATE SO FAR", items[-1]["content"])

    def test_nothing_volatile_in_the_stable_part(self):
        """Timestamps, ids or ordering differences would break the prefix: two identical jobs build identical requests."""
        other = Job().run()
        for ta, tb in zip(self.job.turns, other.turns):
            for ra, rb in zip(ta, tb):
                self.assertEqual(json.dumps(ra, sort_keys=False), json.dumps(rb, sort_keys=False))


class TestCacheKey(unittest.TestCase):
    def test_key_is_set_stable_in_a_job_and_new_after_the_store_clears(self):
        job = Job().run()
        key = job.store[gd_turn.CACHE_KEY]
        self.assertRegex(key, r"^[0-9a-f]{32}$")
        gd_turn.run_turn("again", "Refrigerators", "Acme X1", [], finder=job.f, respond_fn=FakeRespond(["ok " + block(summary="s")]),
                         store=job.store, log_path="")
        self.assertEqual(job.store[gd_turn.CACHE_KEY], key)
        job.store.clear()
        gd_turn.run_turn("again", "Refrigerators", "Acme X1", [], finder=job.f, respond_fn=FakeRespond(["ok " + block(summary="s")]),
                         store=job.store, log_path="")
        self.assertNotEqual(job.store[gd_turn.CACHE_KEY], key)

    def test_app_hands_the_key_to_respond(self):
        src = (ROOT / "rv_techtrack.py").read_text()
        self.assertIn("cache_key=pin_store.get(gd_turn.CACHE_KEY)", src)

    def _respond(self, **kw):
        seen = {}

        class R:
            def create(self, **k):
                seen.update(k)
                return {"output": [], "usage": {}}

        class C:
            responses = R()
        gd_llm.respond([], [], secret_fn=lambda n: "k" if n == "XAI_API_KEY" else None, client_factory=lambda *a, **k: C(), **kw)
        return seen

    def test_respond_sends_prompt_cache_key_only_when_given(self):
        self.assertEqual(self._respond(cache_key="abc")["extra_body"], {"prompt_cache_key": "abc"})
        self.assertNotIn("extra_body", self._respond())
        self.assertNotIn("extra_body", self._respond(cache_key=None))


class TestCachedTokensLogged(unittest.TestCase):
    def test_turn_log_has_cached_tokens_and_share(self):
        usage = {"model": "grok-4.3", "prompt_tokens": 1000, "completion_tokens": 10, "cached_tokens": 640}

        def respond(items, tools, tool_choice=None):
            return {"text": "ok " + block(summary="s"), "calls": [], "output": [], "usage": dict(usage)}
        with tempfile.TemporaryDirectory() as d:
            path = str(pathlib.Path(d) / "gd.log")
            gd_turn.run_turn("hi", "Refrigerators", "Acme X1", [], finder=finder(), respond_fn=respond, store={}, log_path=path)
            rec = json.loads(pathlib.Path(path).read_text().strip().splitlines()[-1])
        self.assertEqual(rec["tokens_cached"], 640)
        self.assertEqual(rec["cached_share"], 0.64)
        self.assertEqual(rec["rounds"][0]["usage"]["cached_tokens"], 640)


def synthetic_job():
    def rec(t, msg, opened, calls, model_calls):
        return {"tech_message": msg, "reply": cache_share_estimate.filler(f"reply-{t}", 1500), "unit": {"category": "Refrigerators", "model_text": "Acme X1"},
                "model_calls": model_calls, "pages_opened": opened, "tool_calls": calls, "cited": [], "web_sources": [],
                "page_images": {"sent": []},
                "rounds": [{"usage": {"prompt_tokens": 7000, "cached_tokens": 0}}]}
    rd = {"call": 1, "tool": "read_pages", "args": {"doc_id": "L1", "pages": ["20"]}, "chars": 12000, "opened": ["L1#20"]}
    return [rec(1, "turn one", [{"doc_id": "L1", "sheet": 20, "chars": 12000}], [rd], 2),
            rec(2, "turn two", [], [], 1), rec(3, "turn three", [], [], 1), rec(4, "turn four", [], [], 1)]


class TestEstimator(unittest.TestCase):
    def test_new_order_caches_more_than_the_old_when_replies_are_long(self):
        """Old: the context (state, summary) sat before the history, so the history was re-sent uncached every turn. New: the
        history is cached up to the last message. Pages after the history (the 'tail' layout) would lose their cache."""
        res = cache_share_estimate.estimate([synthetic_job()])
        self.assertGreater(res["after"]["cached_share"], res["before"]["cached_share"])
        self.assertGreater(res["after"]["cached_share"], res["tail"]["cached_share"])    # pages after the history lose cache
        self.assertEqual(res["jobs"][0]["turns"], 4)


if __name__ == "__main__":
    unittest.main()
