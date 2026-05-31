"""Storage 层使用的领域模型。保持纯数据，不依赖任何后端。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FieldSchema:
    """一列的元信息。后端无关。"""

    field_id: str
    title: str
    type: str  # "text" | "single_select" | "datetime" | "number" | "unknown"
    options: tuple[str, ...] | None = None  # 仅 single_select 有值（option text 列表）
    # 仅 single_select：option_id → option text 的映射。用于 update 响应（API 只回 option_id）
    option_id_to_text: dict[str, str] | None = None


@dataclass
class Record:
    """一行数据。values 用列标题作为 key，已归一化为 Python 类型。"""

    record_id: str
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class BindingEntry:
    """一个番剧的绑定关系。alias 是命令里引用此番剧用的全局唯一键。"""

    alias: str
    group_id: int
    file_id: str
    sheet_id: str
    bound_by: int
    bound_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "file_id": self.file_id,
            "sheet_id": self.sheet_id,
            "bound_by": self.bound_by,
            "bound_at": self.bound_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, alias: str, data: dict[str, Any]) -> "BindingEntry":
        return cls(
            alias=alias,
            group_id=int(data["group_id"]),
            file_id=str(data["file_id"]),
            sheet_id=str(data["sheet_id"]),
            bound_by=int(data["bound_by"]),
            bound_at=datetime.fromisoformat(data["bound_at"]),
        )


@dataclass(frozen=True)
class PipelineStage:
    """流水线里的一道工序。"""

    stage: str
    segment: bool  # True 表示新建集时按 P1/P2/P3 展开；False 只生成「全集」一条
    depends_on: tuple[str, ...]  # 必须先完成的上游工序名

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "segment": self.segment,
            "depends_on": list(self.depends_on),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineStage":
        return cls(
            stage=str(data["stage"]),
            segment=bool(data["segment"]),
            depends_on=tuple(data.get("depends_on") or ()),
        )


Pipeline = list[PipelineStage]
