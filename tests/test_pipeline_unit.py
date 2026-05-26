"""pipeline.py 单元测试 — DSL 解析、默认/覆盖 fallback、快照（D10）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nonebot_plugin_subflow.exceptions import PipelineError
from nonebot_plugin_subflow.models import PipelineStage
from nonebot_plugin_subflow.pipeline import (
    PipelineStore,
    downstream_of,
    parse_dsl,
    predecessors_of,
    stage_names,
    to_dsl,
)


DEFAULT_DSL = "翻译[分段],时轴[分段] → 校对 → 后期 → 监制 → 压制"


# ============================================================ DSL parse


def test_parse_dsl_default_template() -> None:
    pipeline = parse_dsl(DEFAULT_DSL)
    assert stage_names(pipeline) == ["翻译", "时轴", "校对", "后期", "监制", "压制"]
    by_name = {s.stage: s for s in pipeline}
    assert by_name["翻译"].segment is True
    assert by_name["时轴"].segment is True
    assert by_name["校对"].segment is False
    assert by_name["翻译"].depends_on == ()
    assert by_name["时轴"].depends_on == ()
    assert by_name["校对"].depends_on == ("翻译", "时轴")
    assert by_name["后期"].depends_on == ("校对",)
    assert by_name["监制"].depends_on == ("后期",)
    assert by_name["压制"].depends_on == ("监制",)


def test_parse_dsl_single_stage_no_deps() -> None:
    pipeline = parse_dsl("翻译")
    assert len(pipeline) == 1
    assert pipeline[0].stage == "翻译"
    assert pipeline[0].depends_on == ()
    assert pipeline[0].segment is False


def test_parse_dsl_tolerates_half_width_arrow() -> None:
    pipeline = parse_dsl("翻译 -> 校对 => 压制")
    assert stage_names(pipeline) == ["翻译", "校对", "压制"]


def test_parse_dsl_tolerates_full_width_comma_and_brackets() -> None:
    pipeline = parse_dsl("翻译［分段］，时轴［分段］ → 校对")
    assert pipeline[0].segment is True
    assert pipeline[1].segment is True


def test_parse_dsl_tolerates_extra_whitespace() -> None:
    a = parse_dsl("翻译[分段],时轴[分段] → 校对")
    b = parse_dsl("  翻译 [ 分段 ] ,  时轴[分段]→校对  ")
    assert stage_names(a) == stage_names(b)
    assert a[0].segment == b[0].segment


def test_parse_dsl_empty_raises() -> None:
    with pytest.raises(PipelineError):
        parse_dsl("")
    with pytest.raises(PipelineError):
        parse_dsl("   ")


def test_parse_dsl_empty_group_raises() -> None:
    with pytest.raises(PipelineError):
        parse_dsl("翻译 → → 校对")
    with pytest.raises(PipelineError):
        parse_dsl("翻译,,时轴")


def test_parse_dsl_duplicate_stage_raises() -> None:
    with pytest.raises(PipelineError):
        parse_dsl("翻译 → 校对 → 翻译")


def test_parse_dsl_unknown_bracket_annotation_raises() -> None:
    with pytest.raises(PipelineError):
        parse_dsl("翻译[加急] → 校对")


# ============================================================ DSL roundtrip


def test_to_dsl_roundtrips_default_template() -> None:
    pipeline = parse_dsl(DEFAULT_DSL)
    serialized = to_dsl(pipeline)
    pipeline2 = parse_dsl(serialized)
    assert stage_names(pipeline2) == stage_names(pipeline)
    # depends_on 与 segment 也保持
    for a, b in zip(pipeline, pipeline2):
        assert a == b


def test_to_dsl_groups_parallel_stages() -> None:
    pipeline = parse_dsl("翻译,时轴 → 校对")
    assert to_dsl(pipeline) == "翻译,时轴 → 校对"


# ============================================================ graph queries


def test_downstream_of_finds_immediate_dependents() -> None:
    pipeline = parse_dsl(DEFAULT_DSL)
    dn = downstream_of(pipeline, "翻译")
    assert [s.stage for s in dn] == ["校对"]  # 校对的 depends_on 含「翻译」
    dn2 = downstream_of(pipeline, "校对")
    assert [s.stage for s in dn2] == ["后期"]


def test_predecessors_of() -> None:
    pipeline = parse_dsl(DEFAULT_DSL)
    assert predecessors_of(pipeline, "校对") == ("翻译", "时轴")
    assert predecessors_of(pipeline, "翻译") == ()
    assert predecessors_of(pipeline, "不存在") == ()


# ============================================================ PipelineStore


@pytest.fixture
def store(tmp_path: Path) -> PipelineStore:
    return PipelineStore.load(
        config_path=tmp_path / "pipelines.json",
        snapshot_path=tmp_path / "episode_pipelines.json",
        default_pipeline_dsl=DEFAULT_DSL,
    )


def test_get_pipeline_returns_default_when_unset(store: PipelineStore) -> None:
    pipeline = store.get_pipeline("淡岛百景")
    assert stage_names(pipeline) == ["翻译", "时轴", "校对", "后期", "监制", "压制"]


def test_set_pipeline_overrides_default(store: PipelineStore) -> None:
    store.set_pipeline("短片", "翻译 → 校对 → 压制")
    pipeline = store.get_pipeline("短片")
    assert stage_names(pipeline) == ["翻译", "校对", "压制"]
    # 别的番剧仍走 default
    assert stage_names(store.get_pipeline("其他")) == [
        "翻译", "时轴", "校对", "后期", "监制", "压制",
    ]


def test_set_pipeline_persists(tmp_path: Path) -> None:
    cfg = tmp_path / "pipelines.json"
    snap = tmp_path / "episode_pipelines.json"
    s1 = PipelineStore.load(
        config_path=cfg, snapshot_path=snap, default_pipeline_dsl=DEFAULT_DSL
    )
    s1.set_pipeline("短片", "翻译 → 校对")
    s2 = PipelineStore.load(
        config_path=cfg, snapshot_path=snap, default_pipeline_dsl=DEFAULT_DSL
    )
    assert stage_names(s2.get_pipeline("短片")) == ["翻译", "校对"]


def test_remove_pipeline_falls_back_to_default(store: PipelineStore) -> None:
    store.set_pipeline("短片", "翻译 → 压制")
    assert store.has_custom_pipeline("短片")
    assert store.remove_pipeline("短片") is True
    assert not store.has_custom_pipeline("短片")
    assert stage_names(store.get_pipeline("短片")) == [
        "翻译", "时轴", "校对", "后期", "监制", "压制",
    ]


def test_remove_nonexistent_pipeline_returns_false(store: PipelineStore) -> None:
    assert store.remove_pipeline("从未设置") is False


# ============================================================ D10: snapshot


def test_snapshot_and_read_back(store: PipelineStore) -> None:
    pipeline = parse_dsl("翻译 → 压制")
    store.snapshot_episode("淡岛百景", "07", pipeline)
    assert store.has_snapshot("淡岛百景", "07")
    snap = store.get_episode_pipeline("淡岛百景", "07")
    assert stage_names(snap) == ["翻译", "压制"]


def test_get_episode_pipeline_falls_back_when_no_snapshot(
    store: PipelineStore,
) -> None:
    """D10: 快照不存在 → fallback 当前流水线（带 warning 日志）。"""
    pipeline = store.get_episode_pipeline("淡岛百景", "999")
    # 默认 6 阶段
    assert stage_names(pipeline) == [
        "翻译", "时轴", "校对", "后期", "监制", "压制",
    ]


def test_snapshot_isolates_from_pipeline_changes(store: PipelineStore) -> None:
    """D10 核心承诺：改流水线后已有集不受影响。"""
    # /新建集 07：用当前默认流水线快照
    store.snapshot_episode("淡岛百景", "07", store.get_pipeline("淡岛百景"))
    # 之后改流水线
    store.set_pipeline("淡岛百景", "翻译 → 压制")
    # 第 07 集仍走快照，看到的是原来的 6 工序
    snap07 = store.get_episode_pipeline("淡岛百景", "07")
    assert stage_names(snap07) == [
        "翻译", "时轴", "校对", "后期", "监制", "压制",
    ]
    # 第 08 集（无快照）走新流水线
    new = store.get_episode_pipeline("淡岛百景", "08")
    assert stage_names(new) == ["翻译", "压制"]


def test_snapshot_persists(tmp_path: Path) -> None:
    cfg = tmp_path / "pipelines.json"
    snap = tmp_path / "episode_pipelines.json"
    s1 = PipelineStore.load(
        config_path=cfg, snapshot_path=snap, default_pipeline_dsl=DEFAULT_DSL
    )
    s1.snapshot_episode("淡岛百景", "07", parse_dsl("翻译 → 校对"))
    s2 = PipelineStore.load(
        config_path=cfg, snapshot_path=snap, default_pipeline_dsl=DEFAULT_DSL
    )
    assert stage_names(s2.get_episode_pipeline("淡岛百景", "07")) == [
        "翻译", "校对",
    ]


def test_remove_episode_snapshot_falls_back_to_current(
    store: PipelineStore,
) -> None:
    store.snapshot_episode("x", "07", parse_dsl("翻译 → 校对"))
    assert store.remove_episode_snapshot("x", "07") is True
    assert not store.has_snapshot("x", "07")
    # fallback 到当前
    assert stage_names(store.get_episode_pipeline("x", "07")) == [
        "翻译", "时轴", "校对", "后期", "监制", "压制",
    ]


def test_remove_nonexistent_snapshot_returns_false(store: PipelineStore) -> None:
    assert store.remove_episode_snapshot("x", "07") is False


# ============================================================ default pipeline DSL validation


def test_load_with_invalid_default_dsl_raises(tmp_path: Path) -> None:
    with pytest.raises(PipelineError):
        PipelineStore.load(
            config_path=tmp_path / "p.json",
            snapshot_path=tmp_path / "ep.json",
            default_pipeline_dsl="",
        )
