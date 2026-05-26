"""bindings.py 单元测试 — 纯文件 + 内存，不依赖 storage。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from nonebot_plugin_subflow.bindings import BindingStore
from nonebot_plugin_subflow.exceptions import (
    AliasConflictError,
    AliasNotFoundError,
    AmbiguousShowError,
    MainGroupBindError,
    NotBoundError,
)


MAIN_GROUP = 111111111
WORK_GROUP_A = 200000001
WORK_GROUP_B = 200000002
USER = 987654321


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "bindings.json"


@pytest.fixture
def store(store_path: Path) -> BindingStore:
    return BindingStore.load(store_path, main_group_id=MAIN_GROUP)


# ================================================ basic bind / unbind


def test_bind_creates_entry(store: BindingStore) -> None:
    entry = store.bind(
        group_id=WORK_GROUP_A,
        alias="淡岛百景",
        file_id="300000000$abc",
        sheet_id="ss_xxx",
        bound_by=USER,
    )
    assert entry.alias == "淡岛百景"
    assert entry.group_id == WORK_GROUP_A
    assert entry.bound_at <= datetime.now()
    assert store.get("淡岛百景") is entry


def test_bind_persists_across_load(store_path: Path) -> None:
    s1 = BindingStore.load(store_path, main_group_id=MAIN_GROUP)
    s1.bind(
        group_id=WORK_GROUP_A,
        alias="孤独摇滚",
        file_id="f1",
        sheet_id="s1",
        bound_by=USER,
    )
    # reload
    s2 = BindingStore.load(store_path, main_group_id=MAIN_GROUP)
    entry = s2.get("孤独摇滚")
    assert entry is not None
    assert entry.group_id == WORK_GROUP_A
    assert entry.file_id == "f1"


def test_unbind_removes_entry_and_persists(
    store: BindingStore, store_path: Path
) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="x", file_id="f", sheet_id="s", bound_by=USER)
    store.unbind(group_id=WORK_GROUP_A, alias="x")
    assert store.get("x") is None
    # 文件里也没了
    raw = json.loads(store_path.read_text(encoding="utf-8"))
    assert raw["bindings"] == {}


# ================================================ D9: 总群禁绑


def test_main_group_cannot_bind(store: BindingStore) -> None:
    with pytest.raises(MainGroupBindError):
        store.bind(
            group_id=MAIN_GROUP,
            alias="x",
            file_id="f",
            sheet_id="s",
            bound_by=USER,
        )


def test_main_group_cannot_unbind(store: BindingStore) -> None:
    # 先在工作群绑一个
    store.bind(
        group_id=WORK_GROUP_A,
        alias="x",
        file_id="f",
        sheet_id="s",
        bound_by=USER,
    )
    with pytest.raises(MainGroupBindError):
        store.unbind(group_id=MAIN_GROUP, alias="x")


def test_is_main_group(store: BindingStore) -> None:
    assert store.is_main_group(MAIN_GROUP)
    assert not store.is_main_group(WORK_GROUP_A)


# ================================================ D9: 别名全局唯一


def test_alias_conflict_across_groups(store: BindingStore) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="淡岛百景", file_id="f1", sheet_id="s1", bound_by=USER)
    with pytest.raises(AliasConflictError):
        # 另一个群想用同名绑定
        store.bind(group_id=WORK_GROUP_B, alias="淡岛百景", file_id="f2", sheet_id="s2", bound_by=USER)


def test_alias_conflict_same_group(store: BindingStore) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="x", file_id="f1", sheet_id="s1", bound_by=USER)
    with pytest.raises(AliasConflictError):
        store.bind(group_id=WORK_GROUP_A, alias="x", file_id="f2", sheet_id="s2", bound_by=USER)


def test_unbind_wrong_group_raises(store: BindingStore) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="x", file_id="f", sheet_id="s", bound_by=USER)
    with pytest.raises(AliasNotFoundError):
        store.unbind(group_id=WORK_GROUP_B, alias="x")


def test_unbind_unknown_alias_raises(store: BindingStore) -> None:
    with pytest.raises(AliasNotFoundError):
        store.unbind(group_id=WORK_GROUP_A, alias="nope")


# ================================================ queries


def test_get_for_group_lists_only_that_groups_bindings(store: BindingStore) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="a1", file_id="f", sheet_id="s", bound_by=USER)
    store.bind(group_id=WORK_GROUP_A, alias="a2", file_id="f", sheet_id="s2", bound_by=USER)
    store.bind(group_id=WORK_GROUP_B, alias="b1", file_id="f", sheet_id="s3", bound_by=USER)

    a_aliases = {e.alias for e in store.get_for_group(WORK_GROUP_A)}
    b_aliases = {e.alias for e in store.get_for_group(WORK_GROUP_B)}
    assert a_aliases == {"a1", "a2"}
    assert b_aliases == {"b1"}


# ================================================ D9: resolve()


def test_resolve_with_hint_returns_matching_entry(store: BindingStore) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="x", file_id="f", sheet_id="s", bound_by=USER)
    result = store.resolve(group_id=WORK_GROUP_A, hint="x")
    assert result.alias == "x"


def test_resolve_with_hint_rejects_other_groups_binding(store: BindingStore) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="x", file_id="f", sheet_id="s", bound_by=USER)
    with pytest.raises(AliasNotFoundError):
        store.resolve(group_id=WORK_GROUP_B, hint="x")


def test_resolve_with_hint_from_main_group_can_access_any(
    store: BindingStore,
) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="x", file_id="f", sheet_id="s", bound_by=USER)
    # 总群可以查任意番剧
    result = store.resolve(group_id=MAIN_GROUP, hint="x")
    assert result.alias == "x"


def test_resolve_no_hint_single_binding_returns_it(store: BindingStore) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="x", file_id="f", sheet_id="s", bound_by=USER)
    result = store.resolve(group_id=WORK_GROUP_A, hint=None)
    assert result.alias == "x"


def test_resolve_no_hint_multi_binding_raises_ambiguous(store: BindingStore) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="a", file_id="f", sheet_id="s1", bound_by=USER)
    store.bind(group_id=WORK_GROUP_A, alias="b", file_id="f", sheet_id="s2", bound_by=USER)
    with pytest.raises(AmbiguousShowError) as exc:
        store.resolve(group_id=WORK_GROUP_A, hint=None)
    assert set(exc.value.candidates) == {"a", "b"}


def test_resolve_no_hint_unbound_group_raises_not_bound(
    store: BindingStore,
) -> None:
    with pytest.raises(NotBoundError):
        store.resolve(group_id=WORK_GROUP_A, hint=None)


def test_resolve_no_hint_main_group_raises_ambiguous(store: BindingStore) -> None:
    store.bind(group_id=WORK_GROUP_A, alias="x", file_id="f", sheet_id="s", bound_by=USER)
    # 总群没有"本群默认番剧"，无 hint 就必须报歧义
    with pytest.raises(AmbiguousShowError):
        store.resolve(group_id=MAIN_GROUP, hint=None)


def test_resolve_with_unknown_hint_raises(store: BindingStore) -> None:
    with pytest.raises(AliasNotFoundError):
        store.resolve(group_id=WORK_GROUP_A, hint="不存在的番剧")
