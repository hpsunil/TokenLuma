# TokenLuma project notes

- `tokenluma_core.py` contains the local JSONL analysis engine.
- `tokenluma_app.py` is the Streamlit dashboard.
- `tokenluma_bg.svg` is the optional editable background. The app includes a bundled fallback.
- `assets/tokenluma_logo.png` is a standalone source asset; the running app embeds the logo bytes so the PNG is not required at runtime.
- `tokenluma_history.json` is created locally when runs/comparisons are saved; it is intentionally git-ignored.
- No code from `alexgreensh/token-optimizer` has been copied into this project. Review its license before using any of its code in a future implementation.