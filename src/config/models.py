from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LabelConfig:
    name: str
    # reference metadata only -- ds itself doesn't act on `type`/`publish`, it just
    # parses and carries them for other tools (ds-webui's entity type auto-fill,
    # ds-loader's publish-list) that read the same source.json directly; only
    # `archive` has an effect inside ds (routes txn_insert at load time)
    type: str = "text"          # "text" | "number" | "date" | "bool" -- same vocabulary
                                 # ds-webui uses for view.entities[].type
    archive: bool = False       # load straight into transactions_archive, never the active table
    publish: bool = True        # ds-loader's publish stage should include it (not enforced here)
    p: float = 0.5
    description: str | None = None


@dataclass
class SourceConfig:
    name: str
    key_label: str
    p: float = 0.5
    description: str | None = None
    labels: dict[str, LabelConfig] = field(default_factory=dict)
