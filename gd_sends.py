"""One Guided Diagnostics send per tech and message, kept on the server (v4.20.6, Chase go pt1664u, test7b).

v4.20.5 kept the double-send guard in the browser session. In test7b the page reloaded (new session) and the same message
went to Grok again; the first reply, already paid for, never reached the screen because its run was stopped before it
saved the reply. Now, per process and shared by every session:
- claim(): the first send of (user, key) asks Grok; a repeat while it is in flight waits for it; a repeat after it
  finished reuses its reply (no second Grok call). v4.20.9: an in-flight send is held for the whole turn
  (WAIT_SECONDS = the longest possible turn); a finished one is kept KEEP_DONE_SECONDS after that.
- finish(): the reply is kept the moment Grok returns, before anything is drawn.
- take_commit(): exactly one run appends that reply to the chat and saves it to the database.
- unseen(): a finished reply the screen has not drawn yet (its run was stopped), so the next run shows it.
The key is gd_send_key(user, turns before it, message, photo size): a reload starts with the same key, and a later turn
with the same words ("ok") has a different one.
"""
import sys
import threading
import time
import types

MODULE_REVISION = "v4.20.13"

# v4.20.9 (audit M6, Chase t1727u): the guard covers the WHOLE turn. A turn is up to gd_turn.SAFETY_CEILING_CALLS model
# calls, each up to gd_llm.TOOL_REQUEST_TIMEOUT_SEC + DEADLINE_SLACK_SEC, plus the photo read and the library tools
# (TURN_MARGIN_SECONDS). Before, the guard gave up after 240 s, so a press after 4 minutes asked (and paid) Grok twice.
# An in-flight send is held until the asking run finishes or abandons it (never pruned while in flight), and a repeat
# waits that long. A finished reply is kept KEEP_DONE_SECONDS for reuse.
TURN_MARGIN_SECONDS = 180
KEEP_DONE_SECONDS = 600


def max_turn_seconds() -> float:
    import gd_llm
    import gd_turn

    return gd_turn.SAFETY_CEILING_CALLS * (float(gd_llm.TOOL_REQUEST_TIMEOUT_SEC) + float(gd_llm.DEADLINE_SLACK_SEC)) \
        + TURN_MARGIN_SECONDS


WAIT_SECONDS = max_turn_seconds()
TTL_SECONDS = WAIT_SECONDS + KEEP_DONE_SECONDS

_HOLDER = "_techtrack_gd_sends_store"   # kept in sys.modules: survives app reruns and module reloads


class SendStore:
    def __init__(self, ttl=TTL_SECONDS, clock=None):
        self.ttl = ttl
        self.clock = clock or time.time
        self.lock = threading.Lock()
        self.entries = {}

    def _prune(self, now):
        """Finished entries go after ttl; an in-flight one only after the longest possible turn (WAIT_SECONDS) plus ttl,
        so a send is never forgotten while its turn can still be running."""
        for k in [k for k, e in self.entries.items()
                  if now - e["t"] > (self.ttl if e.get("done") else max(self.ttl, WAIT_SECONDS))]:
            self.entries.pop(k, None)

    def claim(self, user, key, wait_s=WAIT_SECONDS):
        """("reuse", entry) when the reply is kept; ("wait", None) while the same send runs elsewhere; ("ask", None) when
        this run is the one to ask Grok (it is marked in flight)."""
        with self.lock:
            now = self.clock()
            self._prune(now)
            e = self.entries.get((user, key))
            if e is not None and e.get("done"):
                return "reuse", dict(e)
            if e is not None and now - e["t"] < wait_s:
                return "wait", None
            self.entries[(user, key)] = {"user": user, "key": key, "t": now, "done": False}
            return "ask", None

    def wait(self, user, key, wait_s=WAIT_SECONDS, poll_s=0.5, sleep=None):
        """The kept entry once the in-flight send finishes; None when it ended without a reply or took too long."""
        sleep = sleep or time.sleep
        end = self.clock() + wait_s
        while True:
            with self.lock:
                e = self.entries.get((user, key))
                if e is not None and e.get("done"):
                    return dict(e)
                if e is None:
                    return None
            if self.clock() >= end:
                return None
            sleep(poll_s)

    def finish(self, user, key, **payload):
        with self.lock:
            e = self.entries.setdefault((user, key), {"user": user, "key": key})
            e.update(payload)
            e.update(done=True, t=self.clock(), committed=e.get("committed", False), seen=False)
            return dict(e)

    def abandon(self, user, key):
        """The asking run ended without a reply: a repeat may ask Grok."""
        with self.lock:
            e = self.entries.get((user, key))
            if e is not None and not e.get("done"):
                self.entries.pop((user, key), None)

    def forget(self, user, key):
        """Drop the send (a "could not reach the AI" reply is never reused: sending again asks again)."""
        with self.lock:
            self.entries.pop((user, key), None)

    def take_commit(self, user, key):
        """True for exactly one caller: that run appends the reply to the chat and saves it."""
        with self.lock:
            e = self.entries.get((user, key))
            if e is None or not e.get("done") or e.get("committed"):
                return False
            e["committed"] = True
            return True

    def update(self, user, key, **fields):
        with self.lock:
            e = self.entries.get((user, key))
            if e is not None:
                e.update(fields)

    def mark_seen(self, user, key):
        self.update(user, key, seen=True)

    def unseen(self, user):
        """Finished replies for this tech the screen has not drawn yet, oldest first."""
        with self.lock:
            self._prune(self.clock())
            return sorted((dict(e) for (u, _k), e in self.entries.items() if u == user and e.get("done") and not e.get("seen")),
                          key=lambda e: e["t"])

    def clear_user(self, user):
        with self.lock:
            for k in [k for k in self.entries if k[0] == user]:
                self.entries.pop(k, None)


def store():
    """The process-wide store (one per server process)."""
    holder = sys.modules.get(_HOLDER)
    if holder is None:
        fresh = types.ModuleType(_HOLDER)
        fresh.store = SendStore()
        holder = sys.modules.setdefault(_HOLDER, fresh)
    return holder.store
