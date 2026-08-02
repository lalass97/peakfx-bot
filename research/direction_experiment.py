from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Direction = Literal["long", "short"]
Mode = Literal["both", "long_only", "short_only"]


@dataclass(frozen=True)
class DirectionExperiment:
    mode: Mode = "both"

    def allows(self, direction: Direction) -> bool:
        if direction not in ("long", "short"):
            raise ValueError("direction must be 'long' or 'short'")
        if self.mode == "both":
            return True
        if self.mode == "long_only":
            return direction == "long"
        if self.mode == "short_only":
            return direction == "short"
        raise ValueError("mode must be 'both', 'long_only', or 'short_only'")


def require_single_change(baseline: DirectionExperiment, candidate: DirectionExperiment) -> None:
    """Fail closed unless the candidate changes only trade direction eligibility."""
    if baseline.mode != "both":
        raise ValueError("baseline mode must be 'both'")
    if candidate.mode != "long_only":
        raise ValueError("candidate mode must be 'long_only'")
