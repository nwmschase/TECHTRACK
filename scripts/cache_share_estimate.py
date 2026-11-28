"""Offline estimate (no API calls): what share of a job's input tokens is a cached prefix, old request order vs new.

v4.20.10 (Chase t1732u). xAI caches the longest start of a request that matches an earlier request (docs.x.ai prompt
caching; billed at $0.20/1M instead of $1.25/1M for grok-4.3). This replays real GD turn logs (the GD_TURN lines of the
11/27 test jobs: tech message, reply, tool calls with their result sizes, pages opened, images sent) through the REAL
request builder (gd_prompt) in both layouts and measures, request by request, how much of the start matches an earlier
request of the same job.

  BEFORE  v4.20.9: [primer, whole job context (unit, pages, lookups, state), history..., new message] (re-read pages moved to the end)
  AFTER   v4.20.10 (gd_prompt.build_input): [primer, pages read, history..., new message, rest of the context], first-read page order
  TAIL    informational only: [primer, history..., new message, whole job context]  (the "everything changing goes last" reading)
  all three then append tool calls/results/images, reminder last

Model, stated plainly: pages / tool results are filler text of the logged size (same in both layouts, so only the ORDER
differs); the state block is approximated by the cited list; one image = IMAGE_TOKENS; characters become tokens at one
ratio calibrated on the first request of each logged job; cache blocks are 128 tokens (the logs show cached_tokens in
multiples of 128); a cold start per job (the first request gets nothing); no eviction or routing misses (the live logs
before prompt_cache_key show both). The tool list is held constant. Server-side web search loops inflate the logged
token counts but are not replayed.

usage: python3 scripts/cache_share_estimate.py LOG [LOG ...]   (files containing GD_TURN {json} lines)
"""
import hashlib
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import gd_prompt  # noqa: E402
import gd_tools  # noqa: E402

IMAGE_TOKENS = 1100
BLOCK = 128
SUMMARY_CHARS = 400
LAYOUTS = ("before", "after", "tail")
PRICE_FULL, PRICE_CACHED = 1.25, 0.20     # $ per 1M input tokens, grok-4.3


def load_jobs(paths):
    """GD_TURN records grouped into jobs: a new job starts when the turn number does not continue or the unit changes."""
    jobs, seen = [], set()
    for path in paths:
        cur = None
        for line in open(path, errors="replace"):
            i = line.find("GD_TURN {")
            if i >= 0:
                body = line[i + 8:]
            elif line.lstrip().startswith('{"ts"'):
                body = line.lstrip()          # a bare JSON turn record (the saved gd_turn_lines.txt form)
            else:
                continue
            try:
                rec = json.loads(body)
            except ValueError:
                continue
            if "rounds" not in rec or not rec.get("tech_message"):
                continue
            ident = (rec.get("ts"), rec.get("turn"), rec.get("tokens_in"))
            if ident in seen:
                continue
            seen.add(ident)
            unit = (rec.get("unit") or {}).get("model_text", "")
            if cur is None or rec.get("turn") != cur[-1].get("turn", 0) + 1 or unit != (cur[-1].get("unit") or {}).get("model_text", ""):
                cur = []
                jobs.append(cur)
            cur.append(rec)
    return jobs


_WORDS = ("the motor wire board fan sensor check test voltage meter reading terminal connector harness replace panel "
          "control relay switch thermostat heat cool flame valve igniter blower circuit fuse ground power supply unit "
          "manual page step measure open closed hot cold slide jack level lock cover screw bracket cable plug pin "
          "should then until before after when with from into over under left right front rear main low high").split()


def filler(key, chars):
    """Deterministic English-like text of exactly `chars` characters (same key = same text)."""
    out, n, i = [], 0, 0
    while n < chars:
        h = hashlib.sha256(f"{key}:{i}".encode()).digest()
        for b in h:
            w = _WORDS[b % len(_WORDS)]
            out.append(w)
            n += len(w) + 1
        i += 1
    return " ".join(out)[:chars]


def _page(doc_id, sheet, chars):
    class P:
        pass
    p = P()
    p.doc_id, p.sheet, p.page, p.title, p.kind, p.reason = doc_id, sheet, str(sheet), doc_id, "support", ""
    p.url = p.doc_number = p.revision = p.note = p.topics = ""
    p.text = filler(f"{doc_id}#{sheet}", max(40, chars))
    p.label = lambda: f"{doc_id}, p.{sheet}"
    return p


def turn_requests(job, layout, r_chars_per_token, tools_json):
    """Every model request of the job, as serialized strings, in order."""
    reqs, hist, read, order, searches, web = [], [], {}, [], [], []
    for t, rec in enumerate(job):
        for o in rec.get("pages_opened") or []:
            key = (o["doc_id"], o["sheet"])
            read[key] = _page(o["doc_id"], o["sheet"], int(o.get("chars") or 0))
            if key in order and layout == "before":       # v4.20.9 moved a re-read page to the end; v4.20.10 keeps first-read order
                order.remove(key)
            if key not in order:
                order.append(key)
        # context as of the START of this turn = what earlier turns read
        pages_now = [read[k] for k in order if k in turn_start_pages(job, t)]
        # The state block is rewritten by Grok every turn (its RUNNING SUMMARY always changes): modelled as the cited pages plus a
        # fresh 400-character summary each turn. The logs do not keep the state block itself.
        state = {"cited": [{"doc_id": c.get("doc_id"), "page": c.get("page")} for c in (job[t - 1].get("cited") or [])] if t else [],
                 "summary": filler(f"summary-{t}", SUMMARY_CHARS)} if t else {}
        parts = dict(user_msg=rec["tech_message"], history=list(hist), category=(rec.get("unit") or {}).get("category", ""),
                     model_text=(rec.get("unit") or {}).get("model_text", ""), pages=pages_now,
                     web_sources=list(web), searches=list(searches), state=state)
        new = gd_prompt.build_input(**parts)
        if layout == "after":
            base = new
        else:       # the whole old context block (pages inside) as one item; BEFORE puts it after the primer, TAIL after the message
            ctx = {"role": "system", "content": gd_prompt.context_block(**{k: v for k, v in parts.items() if k not in ("user_msg", "history")})}
            hist_msgs = [{"role": m["role"], "content": m["content"]} for m in gd_prompt.recent_history(parts["history"])]
            user = {"role": "user", "content": parts["user_msg"]}
            base = [new[0], ctx] + hist_msgs + [user] if layout == "before" else [new[0]] + hist_msgs + [user, ctx]
        calls = {}
        for tc in rec.get("tool_calls") or []:
            if tc.get("side") or tc.get("tool") in (None, "web_search"):
                continue
            calls.setdefault(tc["call"], []).append(tc)
        sent_images = list((rec.get("page_images") or {}).get("sent") or [])
        items = list(base)
        for k in range(1, int(rec.get("model_calls") or 1) + 1):
            reqs.append(tools_json + "\n" + "\n".join(json.dumps(i, ensure_ascii=False) for i in items + [gd_prompt.reminder_item()]))
            for j, tc in enumerate(calls.get(k, [])):
                cid = f"call_{t}_{k}_{j}"
                items.append({"type": "function_call", "call_id": cid, "name": tc["tool"],
                              "arguments": json.dumps(tc.get("args"), sort_keys=True, default=str)})
                items.append({"type": "function_call_output", "call_id": cid, "output": filler(cid, int(tc.get("chars") or 0))})
            n_img = sum(len(tc.get("opened") or []) for tc in calls.get(k, []) if tc["tool"] == "read_pages")
            n_img = min(n_img, len(sent_images))
            if n_img:
                labels, sent_images = sent_images[:n_img], sent_images[n_img:]
                content = [{"type": "input_text", "text": "The app attached the page images ..."}]
                for lab in labels:
                    content.append({"type": "input_image", "detail": "high",
                                    "image_url": "data:image/png;base64," + filler("img:" + lab, int(IMAGE_TOKENS * r_chars_per_token))})
                items.append({"role": "user", "content": content})
        hist += [{"role": "user", "content": rec["tech_message"]}, {"role": "assistant", "content": rec.get("reply") or ""}]
        for tc in rec.get("tool_calls") or []:
            if not tc.get("side") and tc.get("tool"):
                searches.append({"tool": tc["tool"], "args": tc.get("args")})
        for u in rec.get("web_sources") or []:
            if {"url": u} not in web:
                web.append({"url": u})
    return reqs


def turn_start_pages(job, t):
    """(doc_id, sheet) of every page opened in turns BEFORE turn t."""
    return {(o["doc_id"], o["sheet"]) for rec in job[:t] for o in rec.get("pages_opened") or []}


def cached_tokens(reqs, r):
    out = []
    for n, s in enumerate(reqs):
        best = 0
        for prev in reqs[:n]:
            best = max(best, len(os.path.commonprefix([prev, s])))
        out.append(((best / r) // BLOCK) * BLOCK)
    return out


def estimate(jobs):
    """{'before': {...}, 'after': {...}, 'observed': {...}} over all jobs, plus per-job rows."""
    tools_json = json.dumps(gd_tools.TOOL_SPECS)
    ratios = []
    for job in jobs:
        s = turn_requests(job[:1], "after", 4.0, tools_json)[0]
        p1 = job[0]["rounds"][0]["usage"].get("prompt_tokens") or 0
        if p1:
            ratios.append(len(s) / p1)
    r = statistics.median(ratios) if ratios else 4.0
    res = {"chars_per_token": round(r, 2), "jobs": []}
    tot = {k: [0.0, 0.0] for k in LAYOUTS}
    obs = [0, 0]
    for job in jobs:
        row = {"turns": len(job), "requests": sum(int(x.get("model_calls") or 1) for x in job)}
        for layout in LAYOUTS:
            reqs = turn_requests(job, layout, r, tools_json)
            tokens = [len(s) / r for s in reqs]
            cached = cached_tokens(reqs, r)
            row[layout] = round(sum(cached) / sum(tokens), 3)
            tot[layout][0] += sum(cached)
            tot[layout][1] += sum(tokens)
        o_c = sum(int(rd["usage"].get("cached_tokens") or 0) for x in job for rd in x["rounds"])
        o_p = sum(int(rd["usage"].get("prompt_tokens") or 0) for x in job for rd in x["rounds"])
        row["observed"] = round(o_c / o_p, 3) if o_p else None
        obs[0] += o_c
        obs[1] += o_p
        res["jobs"].append(row)
    for layout in LAYOUTS:
        c, n = tot[layout]
        res[layout] = {"cached_share": round(c / n, 3), "input_tokens": round(n),
                       "input_cost_per_1k_jobs_usd": round((n - c) / 1e6 * PRICE_FULL * 1000 + c / 1e6 * PRICE_CACHED * 1000, 2)}
    res["observed"] = {"cached_share": round(obs[0] / obs[1], 3) if obs[1] else None, "prompt_tokens": obs[1]}
    return res


if __name__ == "__main__":
    out = estimate(load_jobs(sys.argv[1:]))
    print(json.dumps(out, indent=2))
