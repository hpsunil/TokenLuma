# Contributing to TokenLuma

Thanks for taking a look at TokenLuma. Small, focused improvements are welcome.

## Set up locally

Use Python 3.10 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the checks before submitting changes:

```bash
python -m unittest discover -s tests -v
python -m py_compile tokenluma_core.py tokenluma_app.py
streamlit run tokenluma_app.py
```

## Pull request guidelines

- Explain the problem and the behavior changed.
- Add or update tests for analysis logic and bug fixes.
- Keep metric labels clear about what is measured, estimated, or heuristic.
- Prefer a small change that can be reviewed and verified.

## Privacy and examples

**Do not commit real Claude Code transcripts.** They may contain prompts, source code, tool output, local paths, and other sensitive details. Use the generated synthetic fixture from `tokenluma_core.demo_transcript_jsonl()` for tests and screenshots. Keep demo data clearly labeled as synthetic.

TokenLuma is local-first, but a hosted deployment processes any transcript uploaded to that host. Do not ask reporters to attach sensitive transcript files to public issues; request a redacted minimal example instead.
