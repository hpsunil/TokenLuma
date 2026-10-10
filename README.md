# TokenLuma

**See the usage. Find the savings.**

TokenLuma is a local-first Streamlit dashboard for inspecting Claude Code session transcripts, understanding where token usage accumulates, and comparing optimization experiments over time.

## What it does

- Reads Claude Code JSONL transcripts from `~/.claude/projects/*/*.jsonl` or from a JSONL file you upload.
- Breaks measured API usage into fresh input, cache reads, cache writes, and output tokens.
- Groups usage by prompt and inspects individual API calls.
- Flags potentially wasteful patterns such as large context additions, repeated file reads, long contexts, verbose replies, and cache misses.
- Provides practical suggestions and before/after examples.
- Saves named experiment runs and comparisons locally to `tokenluma_history.json` so you can track multiple experiments.
- Exports prompt reports, call reports, savings plans, comparisons, and experiment history as CSV.
- Uses a neon orbital visual identity; the generated dots-orbit logo is embedded in the app, and the editable background SVG is included alongside it.

## Quick start

Python 3.10+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
streamlit run tokenluma_app.py
```

Then open the local URL Streamlit prints in your terminal, usually `http://localhost:8501`.

### Test the analysis core

```bash
python -m unittest discover -s tests -v
```

A GitHub Actions workflow runs the unit tests and checks Python syntax on each push and pull request.

## Privacy and data handling

- The app processes transcripts locally and does not intentionally send transcript contents to an external service.
- Transcript uploads are parsed within the local Streamlit process.
- Prompt text and local file paths may be sensitive; treat the UI, CSV exports, and screenshots accordingly.
- Saved experiment history is stored in `tokenluma_history.json` in the app directory. Keep it out of version control; `.gitignore` excludes it.
- `.gitignore` also excludes `*.jsonl` session transcripts and CSV exports to reduce the risk of accidentally committing sensitive data.

## Interpreting metrics

Token usage categories are reported separately. “Token activity” is a sum of selected categories for comparing similar sessions; it is **not** a count of unique tokens. Context-carry exposure and recommendation weights are heuristics, not guaranteed savings. Cost estimates depend on the rates you enter and are not official provider invoices. Verify current model pricing and compare similar tasks, models, tool activity, and cache conditions.

## Architecture and independence

The analysis core is based on the project's own Claude Code JSONL parser and rule-based analysis. TokenLuma is an independent implementation; it does not include source code copied from Token Optimizer. The public Token Optimizer repository was reviewed as product-category reference material only. TokenLuma is not affiliated with or endorsed by that project.

## Before publishing

This repository currently contains the Apache License 2.0 in `LICENSE`. Review that file and ensure it matches your intended redistribution terms before accepting outside contributions or making a commercial release.

## Roadmap ideas

- Track recurring experiment labels and aggregate savings over time.
- Add configurable model-specific pricing presets with clear source/date annotations.
- Add a demo mode using synthetic transcripts so new users can explore without uploading private session data.
- Add more robust benchmark protocols for fair before/after comparisons.