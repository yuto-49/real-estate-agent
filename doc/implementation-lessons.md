# Implementation Lessons — Real Estate Agentic Platform

Captured from the Simulation Visualization feature build (2026-04-01).

---

## 1. Always trace the full data flow before writing a consumer

The visualization endpoint consumed `Property.zip_code` without verifying the model has it. `UserProfile` and `HouseholdProfile` both have `zip_code`, but `Property` does not. The result was an `AttributeError` at runtime that compilation could not catch.

**Rule:** Read the model definition, not just the schema. Before accessing any field on a database model, confirm the column exists in `db/models.py`. Do not assume field names are shared across models.

---

## 2. When modifying a function, check all callers

`persist_simulation_result` has two callers:
- `_run_simulation` (single simulation path)
- `_run_and_persist` (batch simulation path)

The function was updated to store `result.get("transcript", [])`, but only the single-sim caller already had `transcript` in its result dict. The batch caller did not include it, so batch replays always stored an empty transcript.

**Rule:** When changing a function's behavior or expectations, search for every call site (`grep` the function name) and verify each one provides the data the function now depends on.

---

## 3. Background tasks need error handling from day one

FastAPI background tasks are fire-and-forget. Any unhandled exception inside a background task is silently swallowed — no log, no error response, no trace. The simulation appeared to "complete" from the frontend's perspective (the batch status endpoint returned data from the in-memory store), but nothing was ever persisted to the database because the background task crashed.

**Rule:** Always wrap background task bodies in `try/except` with structured logging. This applies to any async fire-and-forget pattern, not just FastAPI's `BackgroundTasks`.

```python
# Bad
async def _run_and_persist():
    result = await batch.run_all()
    await persist(result)

# Good
async def _run_and_persist():
    try:
        result = await batch.run_all()
        await persist(result)
    except Exception as e:
        logger.error("batch.run_failed", error=str(e), exc_info=True)
```

---

## 4. Test the full round-trip, not just compilation

TypeScript and Python both compiled cleanly. All 232 existing tests passed. But the runtime data flow was broken across multiple layers:

- Backend wrote data without the `transcript` field
- Backend accessed a column that does not exist on the model
- Frontend navigated to a page that triggered a 500 from the backend

Static analysis (type checks, unit tests) cannot catch these issues. Integration tests that exercise the actual API endpoints — create a property, run a simulation, persist results, fetch the replay — would have caught all 4 bugs before they reached the user.

**Rule:** After building a feature that spans backend and frontend, write at least one integration test that exercises the full data path: write data, read it back, verify the shape matches what the consumer expects.
