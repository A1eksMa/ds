from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LabelConfig:
    name: str
    p: float = 0.5
    description: str | None = None


@dataclass
class SourceConfig:
    name: str
    key_label: str
    p: float = 0.5
    description: str | None = None
    labels: dict[str, LabelConfig] = field(default_factory=dict)
