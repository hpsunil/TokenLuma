#!/usr/bin/env python3
"""TokenLuma core: per-message token report and saving tips for a Claude Code session.

Reads a Claude Code session transcript (~/.claude/projects/<project>/<session>.jsonl)
and reports MEASURED token usage per API call and per prompt, plus flags with
"avoid / use instead" advice. Nothing is sent anywhere; the file is only read.

Key idea: every API call re-sends the whole conversation. A chunk of text that
enters the context is therefore paid for again on every later call ("carry cost").

Usage:
  tokenluma_core.py                 # latest session under ~/.claude/projects
  tokenluma_core.py SESSION.jsonl   # a specific session
  tokenluma_core.py --calls         # also print every API call
  tokenluma_core.py --json          # machine-readable output
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime

REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)

DEFAULTS = {
    "big_add": 8000,       # tokens added in one step that trigger BIG_ADD
    "cache_miss": 20000,   # cache_creation tokens on a later call that trigger CACHE_MISS
    "long_ctx": 150000,    # context size that triggers LONG_CONTEXT
    "verbose_out": 3000,   # output tokens that trigger VERBOSE_REPLY
    "repeat_read": 2,      # Nth read of the same file that triggers REPEAT_READ
    "idle_gap_s": 300,     # idle gap (seconds) that explains a cache miss (5-minute cache)
}

ADVICE = {
    "Read": ("reading whole or large files",
             "Grep for the lines you need, or Read with offset/limit"),
    "Bash": ("unbounded command output",
             "pipe through head/tail/grep, or use an output-filtering wrapper"),
    "WebFetch": ("fetching full pages",
                 "search first, then fetch with a narrow extraction prompt"),
    "WebSearch": ("broad searches with long results",
                  "use more specific queries"),
    "prompt": ("pasting large text or attaching big files",
               "refer to a file path and paste only the relevant part"),
    "default": ("large tool results",
                "narrow the request so less text comes back"),
}


def parse_ts(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def tool_label(name, inp):
    inp = inp if isinstance(inp, dict) else {}
    if name in ("Read", "Edit", "Write", "NotebookEdit"):
        arg = inp.get("file_path") or inp.get("notebook_path")
    elif name == "Bash":
        arg = inp.get("command")
    elif name in ("Grep", "Glob"):
        arg = inp.get("pattern")
    elif name == "WebFetch":
        arg = inp.get("url")
    elif name == "WebSearch":
        arg = inp.get("query")
    else:
        arg = None
    arg = (arg or "").replace("\n", " ")
    if len(arg) > 50:
        arg = arg[:50] + "…"
    return f"{name}: {arg}" if arg else name


def find_latest_session():
    files = glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl"))
    return max(files, key=os.path.getmtime) if files else None


def load_session(path, include_sidechain=False):
    """Return (calls, prompts, skipped_lines). Each API call is counted once."""
    events, bad = [], 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1

    calls, by_id, prompts = [], {}, []
    pending_prompt = False
    for ev in events:
        etype = ev.get("type")
        if etype not in ("user", "assistant"):
            continue
        if ev.get("isSidechain") and not include_sidechain:
            continue
        msg = ev.get("message")
        if not isinstance(msg, dict):
            continue

        if etype == "user":
            content = msg.get("content")
            if isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            ):
                continue  # a tool result, not something the person typed
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = " ".join(
                    b.get("text", "") for b in content
                    if isinstance(b, dict) and b.get("type") == "text"
                )
            else:
                text = ""
            if ev.get("isMeta") or not text.strip():
                continue
            # Claude Code injects <system-reminder> blocks; show what the person typed.
            shown = REMINDER_RE.sub("", text).strip() or "(system message)"
            prompts.append({"text": shown, "ts": parse_ts(ev.get("timestamp"))})
            pending_prompt = True
            continue

        usage, mid = msg.get("usage"), msg.get("id")
        if not isinstance(usage, dict) or not mid:
            continue
        if mid not in by_id:
            call = {
                "id": mid,
                "ts": parse_ts(ev.get("timestamp")),
                "model": msg.get("model"),
                "usage": usage,
                "tools": [],
                "_tool_ids": set(),
                "prompt_idx": len(prompts) - 1,
                "after_prompt": pending_prompt,
            }
            pending_prompt = False
            by_id[mid] = call
            calls.append(call)
        call = by_id[mid]
        content = msg.get("content")
        if isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    bid = b.get("id")
                    if bid in call["_tool_ids"]:
                        continue
                    call["_tool_ids"].add(bid)
                    call["tools"].append({
                        "name": b.get("name", "?"),
                        "label": tool_label(b.get("name", "?"), b.get("input")),
                        "file": (b.get("input") or {}).get("file_path")
                        if b.get("name") == "Read" else None,
                    })
    for c in calls:
        del c["_tool_ids"]
    return calls, prompts, bad


def analyze(calls, cfg):
    n = len(calls)
    prev_ctx, prev_call = 0, None
    reads = {}
    long_flagged = False
    for i, c in enumerate(calls):
        u = c["usage"]
        c["input"] = u.get("input_tokens") or 0
        c["cache_read"] = u.get("cache_read_input_tokens") or 0
        c["cache_create"] = u.get("cache_creation_input_tokens") or 0
        c["output"] = u.get("output_tokens") or 0
        c["ctx"] = c["input"] + c["cache_read"] + c["cache_create"]
        c["fresh"] = c["input"] + c["cache_create"]
        c["growth"] = c["ctx"] - prev_ctx
        c["rereads"] = n - i - 1
        c["carry"] = max(c["growth"], 0) * c["rereads"]

        if i == 0:
            c["source_kind"], c["source"] = "baseline", "session start (system prompt, tools, memory files)"
        elif c["after_prompt"]:
            c["source_kind"], c["source"] = "prompt", "your message"
        elif prev_call and prev_call["tools"]:
            c["source_kind"] = prev_call["tools"][0]["name"]
            c["source"] = ", ".join(t["label"] for t in prev_call["tools"][:3])
        else:
            c["source_kind"], c["source"] = "reply", "assistant reply"

        c["gap_s"] = None
        if prev_call and c["ts"] and prev_call["ts"]:
            c["gap_s"] = (c["ts"] - prev_call["ts"]).total_seconds()

        flags = []
        if i > 0 and c["growth"] >= cfg["big_add"]:
            avoid, use = ADVICE.get(c["source_kind"], ADVICE["default"])
            flags.append({
                "code": "BIG_ADD", "weight": c["carry"],
                "msg": f"{c['source']} added {c['growth']:,} tokens; re-read on {c['rereads']} later call(s) (carry {c['carry']:,})",
                "avoid": avoid, "use": use,
            })
        # cache_creation also holds NEWLY added content, so it is not a miss by itself.
        # A real miss: less was read from cache than the previous call's whole context.
        missed = max(0, prev_ctx - c["cache_read"]) if i > 0 else 0
        c["cache_missed"] = missed
        if missed >= cfg["cache_miss"]:
            if c["gap_s"] is not None and c["gap_s"] >= cfg["idle_gap_s"]:
                why = f"after an idle gap of {int(c['gap_s'] // 60)} min (cache expired)"
                use = "keep working in bursts, or start a fresh chat if you were away"
            else:
                why = "without a long idle gap (earlier context probably changed)"
                use = "avoid editing early context (CLAUDE.md, settings, tool set) mid-session"
            flags.append({
                "code": "CACHE_MISS", "weight": missed,
                "msg": f"{missed:,} tokens of earlier context were not read from cache {why}",
                "avoid": "cache rewrites of a large context", "use": use,
            })
        if c["ctx"] >= cfg["long_ctx"] and not long_flagged:
            long_flagged = True  # flag once, at the first call that crosses the line
            flags.append({
                "code": "LONG_CONTEXT", "weight": c["ctx"],
                "msg": f"context crossed {cfg['long_ctx']:,} tokens here ({c['ctx']:,}); "
                       f"each later call re-reads all of it",
                "avoid": "carrying unrelated history forward",
                "use": "/compact, or start a new chat for unrelated work",
            })
        if c["output"] >= cfg["verbose_out"]:
            flags.append({
                "code": "VERBOSE_REPLY", "weight": c["output"],
                "msg": f"reply used {c['output']:,} output tokens (includes thinking)",
                "avoid": "open-ended requests for long answers",
                "use": "ask for a short answer or a specific format",
            })
        for t in c["tools"]:
            if t["name"] == "Read" and t["file"]:
                reads[t["file"]] = reads.get(t["file"], 0) + 1
                if reads[t["file"]] == cfg["repeat_read"]:
                    flags.append({
                        "code": "REPEAT_READ", "weight": c["growth"] if c["growth"] > 0 else 0,
                        "msg": f"{t['file']} read {reads[t['file']]} times",
                        "avoid": "re-reading a file already in context",
                        "use": "refer back to it, or Grep for the specific lines",
                    })
        c["flags"] = flags
        prev_ctx, prev_call = c["ctx"], c


def by_prompt(calls, prompts):
    groups = {}
    for c in calls:
        groups.setdefault(c["prompt_idx"], []).append(c)
    rows = []
    for idx in sorted(groups):
        cs = groups[idx]
        text = prompts[idx]["text"] if idx >= 0 else "(session start)"
        rows.append({
            "prompt": idx + 1 if idx >= 0 else 0,
            "text": text.replace("\n", " "),
            "calls": len(cs),
            "new_context": sum(max(c["growth"], 0) for c in cs),
            "reread": sum(c["cache_read"] for c in cs),
            "fresh": sum(c["fresh"] for c in cs),
            "output": sum(c["output"] for c in cs),
            "ctx_end": cs[-1]["ctx"],
            "flags": sorted({f["code"] for c in cs for f in c["flags"]}),
        })
    return rows


def totals(calls):
    ctx_sum = sum(c["ctx"] for c in calls)
    cr = sum(c["cache_read"] for c in calls)
    return {
        "calls": len(calls),
        "fresh_input": sum(c["input"] for c in calls),
        "cache_write": sum(c["cache_create"] for c in calls),
        "cache_read": cr,
        "output": sum(c["output"] for c in calls),
        "context_now": calls[-1]["ctx"] if calls else 0,
        "reread_share": (cr / ctx_sum) if ctx_sum else 0.0,
    }


def render(path, calls, rows, tot, bad, args):
    out = []
    models = sorted({c["model"] for c in calls if c["model"]})
    out.append(f"Session: {path}")
    out.append(f"Models: {', '.join(models) or 'unknown'} | API calls: {tot['calls']} | prompts: {len(rows)}"
               + (f" | unreadable lines skipped: {bad}" if bad else ""))
    out.append("")
    out.append("TOTALS (measured, each API call counted once)")
    out.append(f"  fresh input  {tot['fresh_input']:>12,}    cache write {tot['cache_write']:>12,}")
    out.append(f"  cache read   {tot['cache_read']:>12,}    output      {tot['output']:>12,}")
    out.append(f"  context now  {tot['context_now']:>12,}    re-read share of all input: {tot['reread_share']:.0%}")
    out.append("")
    out.append("PER PROMPT")
    out.append(f"  {'#':>3} {'calls':>5} {'new ctx':>9} {'re-read':>11} {'fresh':>9} {'output':>8} {'ctx end':>9}  prompt / flags")
    for r in rows:
        txt = r["text"][: args.preview] + ("…" if len(r["text"]) > args.preview else "") if args.preview else ""
        fl = (" [" + ",".join(r["flags"]) + "]") if r["flags"] else ""
        out.append(f"  {r['prompt']:>3} {r['calls']:>5} {r['new_context']:>9,} {r['reread']:>11,} "
                   f"{r['fresh']:>9,} {r['output']:>8,} {r['ctx_end']:>9,}  {txt}{fl}")
    if args.calls:
        out.append("")
        out.append("PER API CALL")
        out.append(f"  {'#':>3} {'ctx':>9} {'growth':>9} {'cache rd':>9} {'fresh':>8} {'output':>7}  added by")
        for i, c in enumerate(calls, 1):
            out.append(f"  {i:>3} {c['ctx']:>9,} {c['growth']:>9,} {c['cache_read']:>9,} "
                       f"{c['fresh']:>8,} {c['output']:>7,}  {c['source'][:60]}")
    flags = [(f, i) for i, c in enumerate(calls, 1) for f in c["flags"]]
    flags.sort(key=lambda t: t[0]["weight"], reverse=True)
    out.append("")
    out.append(f"FLAGS (top {min(args.top, len(flags))} of {len(flags)}, biggest first)")
    if not flags:
        out.append("  none: nothing crossed the thresholds")
    for f, i in flags[: args.top]:
        out.append(f"  [{f['code']}] call {i}: {f['msg']}")
        out.append(f"      avoid: {f['avoid']}")
        out.append(f"      use:   {f['use']}")
    out.append("")
    out.append("Notes: 'growth' = change in total context vs the previous call. 'carry' = growth x later calls that re-read it.")
    out.append("Cache reads are billed at a lower rate than fresh input; check current pricing for your model.")
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description="Per-message token report for a Claude Code session")
    p.add_argument("session", nargs="?", help="session .jsonl (default: most recent)")
    p.add_argument("--calls", action="store_true", help="also list every API call")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument("--top", type=int, default=10, help="how many flags to show")
    p.add_argument("--preview", type=int, default=50, help="chars of each prompt to show (0 hides)")
    p.add_argument("--include-sidechain", action="store_true", help="include subagent calls")
    for k, v in DEFAULTS.items():
        p.add_argument("--" + k.replace("_", "-"), type=int, default=v)
    args = p.parse_args(argv)

    path = args.session or find_latest_session()
    if not path or not os.path.exists(path):
        sys.exit("no session file found; pass a path to a .jsonl transcript")
    cfg = {k: getattr(args, k) for k in DEFAULTS}

    calls, prompts, bad = load_session(path, args.include_sidechain)
    if not calls:
        sys.exit("no API calls with usage data found in this file")
    analyze(calls, cfg)
    rows, tot = by_prompt(calls, prompts), totals(calls)

    if args.json:
        slim = [{k: (v.isoformat() if hasattr(v, "isoformat") else v)
                 for k, v in c.items() if k not in ("usage",)} for c in calls]
        print(json.dumps({"session": path, "totals": tot, "prompts": rows, "calls": slim},
                         indent=2, default=str))
    else:
        print(render(path, calls, rows, tot, bad, args))


if __name__ == "__main__":
    main()