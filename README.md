# gamagori-controller v0.4.1 LIVE TRANSPORT SHADOW

Shadow-only controller for deadline-aware monitoring of BOAT RACE Gamagori.

## Safety / scope

- `DRY_RUN=true` is mandatory; v0.4.1 contains no Production Airtable adapter.
- Official data is never guessed. Parser/source failures become missing/error states.
- Closing predictions and A/B baseline references are still mocked; this version validates transport, timing, state transitions, persistence and auditability.
- Local SQLite is durable on Render only when `STATE_DB_PATH` is placed under a mounted Persistent Disk (Blueprint uses `/var/data`).

## Run tests

```bash
pytest -q
```

## Run locally

```bash
cp .env.example .env
# export variables as needed
python main.py
```
