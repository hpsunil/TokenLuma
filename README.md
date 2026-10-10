# TokenLuma 🪐

**See where the tokens go. Learn what to improve.**

TokenLuma is a local-first dashboard for understanding token usage in Claude Code sessions. It turns raw session transcripts into readable charts, prompt-level reports, API-call details, and practical ideas for reducing unnecessary context and repeated work.

**Built by [@hpsunil](https://github.com/hpsunil)** — an independent developer learning by building practical tools and sharing the journey in public.

[![Tests](https://github.com/hpsunil/TokenLuma/actions/workflows/tests.yml/badge.svg)](https://github.com/hpsunil/TokenLuma/actions/workflows/tests.yml)

## Why TokenLuma exists

When working with an AI coding assistant, it can be difficult to see where token usage is going: large file reads, repeated context, long conversations, cache behavior, or responses that are larger than needed. TokenLuma gives you a clearer view of usage recorded by Claude Code so you can investigate patterns and test whether a change helped.

The goal is practical learning—not a magic “save tokens” button. TokenLuma points out patterns worth reviewing, explains why they might matter, and lets you compare similar sessions before and after an experiment.

## What it does

- **Usage overview:** summarizes recorded input, cache read, cache write, and output token categories.
- **Prompt-level analysis:** shows which prompts and follow-up API calls are associated with usage.
- **API-call inspection:** lets you investigate context, growth, cache activity, output, tool activity, and timestamps.
- **Saving opportunities:** highlights patterns such as large context additions, repeated reads, long contexts, verbose replies, and cache misses using the project's rule-based analysis.
- **Actionable examples:** offers ideas like searching for a specific function instead of reading a large file, narrowing command output, or asking for a shorter response.
- **Cost estimates:** estimates cost using rates you enter. The values are estimates, not official billing.
- **Before/after experiments:** save named runs, compare two runs, and record comparisons across multiple experiments. Demo sessions cannot be saved into experiment history.
- **CSV exports:** export reports and experiment history for further analysis.
- **Neon UI:** dark, orbital-inspired design with a custom background and a built-in dots-orbit logo.

## How it works

1. **Choose a transcript source.** TokenLuma can inspect local Claude Code session files under `~/.claude/projects/*/*.jsonl`, or you can upload a JSONL transcript in the app.
2. **Parse recorded usage.** The analysis core reads usage fields in each API call, associates calls with prompts and tool activity, and skips malformed lines it cannot parse.
3. **Apply transparent rules.** Configurable thresholds identify patterns that may deserve a closer look.
4. **Review the evidence.** Open a prompt or API call to understand what was observed before changing your workflow.
5. **Run an experiment.** Try one focused change, save the follow-up session, and compare it with a similar baseline.
6. **Keep the history.** Saved runs and comparisons live in a local `tokenluma_history.json` file, which is excluded from Git by `.gitignore`.

## Quick start

Python 3.10 or newer is recommended.

```bash
git clone https://github.com/hpsunil/TokenLuma.git
cd TokenLuma

python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run tokenluma_app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`.

### Explore with Demo mode

If no local Claude Code sessions are found, TokenLuma opens **Demo mode** automatically. The built-in transcript is synthetic and includes example context growth, repeated reads, a long reply, and a cache-expiry gap so the charts and warnings have something to show. All demo prompts, paths, timestamps, and token counts are labeled as synthetic; they are not measurements or pricing guidance.

Choose **Latest/local session** to inspect a real local session, or **Upload JSONL** to load a transcript you have selected. A transcript can contain prompts, code, tool output, and local file paths, so only use files you are comfortable inspecting locally.
### Run the tests

```bash
python -m unittest discover -s tests -v
python -m py_compile tokenluma_core.py tokenluma_app.py
```

GitHub Actions runs the tests and syntax check on each push and pull request.

## Project guides

- [Contributing](CONTRIBUTING.md) — local setup, tests, and pull request guidance.
- [Security policy](SECURITY.md) — how to report security concerns safely.
- [Changelog](CHANGELOG.md) — user-visible changes.
- [Issue templates](https://github.com/hpsunil/TokenLuma/issues/new/choose) — report a bug or suggest an improvement.

## Demo mode and privacy

Demo mode uses a built-in synthetic transcript and does not need access to your own session files. Analysis of real transcripts happens locally in the Streamlit process; TokenLuma does not intentionally upload transcript contents to a remote service. If you host the app on a server, remember that any uploaded file is processed on that server—use a trusted deployment and avoid public hosting for sensitive data.

## What the numbers mean

| Metric | Meaning |
|---|---|
| Fresh input | Input tokens recorded for API calls, summed across the selected session. |
| Cache reads | Cache-read input tokens recorded across API calls. |
| Cache writes | Cache-creation input tokens recorded across API calls. |
| Output | Output tokens recorded across API calls; the source data may include model thinking tokens. |
| Context | The app's per-call context calculation based on input and cache-related fields. |
| Context growth | Change in the calculated context compared with the previous API call. |
| Carry exposure | A heuristic based on positive context growth multiplied by later calls; it is not a precise billable total or guaranteed savings. |
| Estimated cost | A calculation based on prices entered in the UI. Confirm your current provider, model, cache, and output pricing separately. |

**Important:** Token categories are displayed separately. A summed “token activity” figure is useful only as a comparison metric for similar runs; it is not a count of unique tokens. Changes between two sessions do not prove that one recommendation caused the difference. For fair comparisons, keep the task, model, tool activity, and cache conditions as similar as possible.

## Privacy

TokenLuma is designed to process session data locally in the Streamlit process. It does not need an AI API key and does not intentionally send transcript contents to an external service.

- The app may display prompt text, code-related paths, or tool details from a transcript. Treat screenshots and exports as sensitive.
- Saved experiment history is written to `tokenluma_history.json` next to the app.
- Session transcript files (`*.jsonl`), local history, and CSV exports are excluded by `.gitignore` to reduce the risk of accidental commits.
- Review `.gitignore` before adding new data or test fixtures. Use synthetic test data in the public repository.

## Project layout

```text
TokenLuma/
├── tokenluma_app.py             # Streamlit UI
├── tokenluma_core.py            # Transcript parser and analysis rules
├── tokenluma_bg.svg             # Editable background (embedded fallback is included)
├── requirements.txt             # Python dependencies
├── tests/
│   └── test_tokenluma_core.py   # Core unit tests
├── .github/
│   └── workflows/
│       └── tests.yml            # CI checks
├── .gitignore
└── README.md
```

## About the developer

Hi! I'm [@hpsunil](https://github.com/hpsunil), an independent developer learning by building useful software. I'm using TokenLuma to learn more about Python, data analysis, product design, automated testing, and how small ideas become tools that other developers can try.

This is a work in progress, built step by step. I want to share what I'm learning, be clear about the limits of the metrics, and improve the project through real feedback. If you spot a bug, have a question, or see a way to make TokenLuma more helpful, please open an issue or suggest an improvement. You don't need to be an expert to start learning or contribute.

## Scope and independence

TokenLuma is an independent project. It does not include code copied from [Token Optimizer](https://github.com/alexgreensh/token-optimizer); that repository was considered reference material for understanding the broader problem space. TokenLuma is not affiliated with or endorsed by that project.

## License

This repository currently contains the Apache License 2.0 in `LICENSE`. Read it before reusing or redistributing the source. The license does not grant permission to use third-party trademarks or unrelated assets.

## Ideas for future improvements

- Demo mode with synthetic transcripts, so new users can explore safely.
- Model-specific pricing presets with source links and “last checked” dates.
- Summary reports that track repeated experiments and trends over time.
- More benchmark guidance for comparing equivalent tasks fairly.
- Additional beginner-friendly explanations for token and cache concepts.
