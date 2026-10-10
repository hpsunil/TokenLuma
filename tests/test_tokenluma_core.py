import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import tokenluma_core as tc  # noqa: E402


def user_prompt(text, ts):
    return {"type": "user", "isSidechain": False, "timestamp": ts,
            "message": {"role": "user", "content": text}}


def tool_result(ts):
    return {"type": "user", "isSidechain": False, "timestamp": ts,
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "..."}]}}


def assistant(mid, ts, usage, blocks):
    # Claude Code writes one line per content block, repeating id and usage.
    return [{"type": "assistant", "isSidechain": False, "timestamp": ts,
             "message": {"id": mid, "model": "m", "role": "assistant", "usage": usage, "content": [b]}}
            for b in blocks]


def usage(inp, cr, cc, out):
    return {"input_tokens": inp, "cache_read_input_tokens": cr,
            "cache_creation_input_tokens": cc, "output_tokens": out}


def tool_use(tid, name, **inp):
    return {"type": "tool_use", "id": tid, "name": name, "input": inp}


def build_session():
    L = []
    L.append(user_prompt("fix the bug", "2026-01-01T10:00:00Z"))
    # call 1: baseline context 20,000; reads big.py (two blocks, same id/usage -> counted once)
    L += assistant("a1", "2026-01-01T10:00:05Z", usage(10, 0, 19990, 100),
                   [{"type": "text", "text": "ok"}, tool_use("t1", "Read", file_path="/p/big.py")])
    L.append(tool_result("2026-01-01T10:00:06Z"))
    # call 2: context grows by 15,000 (the file) -> BIG_ADD from Read
    L += assistant("a2", "2026-01-01T10:00:10Z", usage(10, 20000, 15000, 200),
                   [tool_use("t2", "Read", file_path="/p/big.py")])
    L.append(tool_result("2026-01-01T10:00:11Z"))
    # call 3: small growth; re-reads the same file -> REPEAT_READ on call 2 (2nd read)
    L += assistant("a3", "2026-01-01T10:00:15Z", usage(10, 35000, 300, 4000),
                   [{"type": "text", "text": "long answer"}])
    # new prompt after a 10-minute idle gap; large cache rewrite -> CACHE_MISS (idle gap)
    L.append(user_prompt("now something else", "2026-01-01T10:12:00Z"))
    L += assistant("a4", "2026-01-01T10:12:05Z", usage(10, 0, 160000, 50),
                   [{"type": "text", "text": "done"}])
    return L


class TokenLumaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
        for ev in build_session():
            self.tmp.write(json.dumps(ev) + "\n")
        self.tmp.write("not json\n")
        self.tmp.close()
        self.calls, self.prompts, self.bad = tc.load_session(self.tmp.name)
        tc.analyze(self.calls, tc.DEFAULTS)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_each_call_counted_once_and_bad_lines_skipped(self):
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(self.bad, 1)
        self.assertEqual(len(self.prompts), 2)

    def test_context_and_growth(self):
        ctx = [c["ctx"] for c in self.calls]
        self.assertEqual(ctx, [20000, 35010, 35310, 160010])
        self.assertEqual([c["growth"] for c in self.calls], [20000, 15010, 300, 124700])

    def test_carry_cost(self):
        self.assertEqual(self.calls[1]["rereads"], 2)
        self.assertEqual(self.calls[1]["carry"], 15010 * 2)

    def test_big_add_blames_the_read(self):
        f = [x for x in self.calls[1]["flags"] if x["code"] == "BIG_ADD"]
        self.assertEqual(len(f), 1)
        self.assertIn("Read", f[0]["msg"])
        self.assertIn("Grep", f[0]["use"])

    def test_baseline_not_flagged_as_big_add(self):
        self.assertFalse([x for x in self.calls[0]["flags"] if x["code"] == "BIG_ADD"])

    def test_repeat_read(self):
        codes = [x["code"] for x in self.calls[1]["flags"]]
        self.assertIn("REPEAT_READ", codes)

    def test_verbose_reply(self):
        self.assertIn("VERBOSE_REPLY", [x["code"] for x in self.calls[2]["flags"]])

    def test_cache_miss_after_idle_gap(self):
        f = [x for x in self.calls[3]["flags"] if x["code"] == "CACHE_MISS"]
        self.assertEqual(len(f), 1)
        self.assertIn("idle gap", f[0]["msg"])

    def test_new_content_in_cache_creation_is_not_a_miss(self):
        # call 2 wrote 15,000 NEW tokens to cache but still read all 20,000 old ones
        self.assertEqual(self.calls[1]["cache_missed"], 0)
        self.assertNotIn("CACHE_MISS", [x["code"] for x in self.calls[1]["flags"]])

    def test_long_context(self):
        self.assertIn("LONG_CONTEXT", [x["code"] for x in self.calls[3]["flags"]])

    def test_long_context_flagged_once(self):
        # push a 5th call that is also over the threshold
        calls = [dict(c) for c in self.calls]
        extra = dict(calls[-1], id="a5", after_prompt=False,
                     usage=usage(10, 160010, 100, 50), flags=[])
        calls.append(extra)
        tc.analyze(calls, tc.DEFAULTS)
        n = sum(1 for c in calls for f in c["flags"] if f["code"] == "LONG_CONTEXT")
        self.assertEqual(n, 1)

    def test_prompt_preview_strips_system_reminders(self):
        events = [user_prompt("<system-reminder>noise</system-reminder>\nreal question", "2026-01-01T10:00:00Z")]
        events += assistant("z1", "2026-01-01T10:00:01Z", usage(1, 0, 10, 1), [{"type": "text", "text": "x"}])
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
        try:
            _, prompts, _ = tc.load_session(f.name)
        finally:
            os.unlink(f.name)
        self.assertEqual(prompts[0]["text"], "real question")

    def test_totals_and_prompt_rows(self):
        t = tc.totals(self.calls)
        self.assertEqual(t["output"], 100 + 200 + 4000 + 50)
        self.assertEqual(t["cache_read"], 0 + 20000 + 35000 + 0)
        rows = tc.by_prompt(self.calls, self.prompts)
        self.assertEqual([r["calls"] for r in rows], [3, 1])
        self.assertEqual(rows[0]["output"], 4300)


    def test_demo_transcript_is_synthetic_and_analyzable(self):
        raw = tc.demo_transcript_jsonl()
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", encoding="utf-8", delete=False) as f:
            f.write(raw)
            path = f.name
        try:
            calls, prompts, bad = tc.load_session(path)
            tc.analyze(calls, tc.DEFAULTS)
            totals = tc.totals(calls)
            flags = {flag["code"] for call in calls for flag in call["flags"]}
        finally:
            os.unlink(path)
        self.assertEqual(bad, 0)
        self.assertEqual(len(calls), 5)
        self.assertEqual(len(prompts), 2)
        self.assertGreater(totals["cache_read"], 0)
        self.assertGreater(totals["cache_write"], 0)
        self.assertTrue({"BIG_ADD", "CACHE_MISS", "LONG_CONTEXT", "VERBOSE_REPLY"} <= flags)
        self.assertIn("/sample-app/services/client.py", raw)
        self.assertNotIn("~/.claude/projects/", raw)


if __name__ == "__main__":
    unittest.main()