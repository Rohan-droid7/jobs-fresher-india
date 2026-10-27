"""Indeed connector — disabled."""

from __future__ import annotations

from ..models import Job
from ..net import Net


async def fetch(company: dict, net: Net) -> list[Job]:
    """Disabled connector."""
    return []
