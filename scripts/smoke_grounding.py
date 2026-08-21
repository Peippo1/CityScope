"""Opt-in end-to-end smoke test; never run automatically in CI."""

from __future__ import annotations

import asyncio

from apps.api.app.agent.schemas import InvestigationRequest
from apps.api.app.agent.service import InvestigationService


async def main() -> None:
    result = await InvestigationService().investigate(InvestigationRequest(
        question="Which of the busiest cycling areas have relatively few cafes nearby?"
    ))
    print(result.model_dump_json(indent=2))
    if result.status not in {"answered", "partial"}:
        raise SystemExit("Grounding smoke test did not complete")


if __name__ == "__main__":
    asyncio.run(main())
