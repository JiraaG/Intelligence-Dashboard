# radar-lint

```bash
# Python (from radar/backend or path to file)
ruff check <path.py>

# Frontend (from radar/frontend)
npx prettier --check <file>
```

Or invoke Radar hooks manually:

```bash
# Pre (stdin JSON tool payload)
python radar/.ecc/hooks/pre-tool-use.py

# Post (write tool payload with path)
python radar/.ecc/hooks/post-tool-use.py
```

Cursor auto-wiring: `.cursor/hooks.json` → adapters → same scripts.
