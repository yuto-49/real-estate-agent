"""Local HTTP shim for ``MIROFISH_MODE=live`` during development.

The full MiroFish simulation service is **not included in this repository**; the
platform talks to it over HTTP (``GET /health``, ``POST /api/simulate``). This
script runs a tiny FastAPI app on port **5001** that delegates to
``MockMiroFishClient``, so report generation succeeds with ``live`` mode without
the real MiroFish stack.

From the ``real-estate-agent/`` directory:

    python scripts/dev_mirofish_stub.py

Keep ``MIROFISH_API_URL=http://localhost:5001`` and ``MIROFISH_MODE=live`` in ``.env``.
For day-to-day work you can instead set ``MIROFISH_MODE=mock`` and skip this process.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python scripts/dev_mirofish_stub.py` without editable install quirks
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from pydantic import BaseModel, Field

from intelligence.mirofish_client import MockMiroFishClient

app = FastAPI(title="MiroFish dev shim", version="0.0.0")


class SimulateRequest(BaseModel):
    seed: str
    question: str = "What is the best investment strategy for this buyer?"
    ticks: int = Field(default=30, ge=1, le=120)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/simulate")
async def simulate(body: SimulateRequest) -> dict:
    client = MockMiroFishClient()
    try:
        report = await client.run_simulation(body.seed, body.question, body.ticks)
        return report.raw_json if report.raw_json else {}
    finally:
        await client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
