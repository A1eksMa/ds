from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> float: ...  # Unix timestamp (seconds, float)
