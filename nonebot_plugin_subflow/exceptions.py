"""Storage 层异常类。"""

from __future__ import annotations


class StorageError(Exception):
    """存储后端错误的基类。"""

    def __init__(self, message: str, *, ret: int | None = None) -> None:
        super().__init__(message)
        self.ret = ret


class TokenExpiredError(StorageError):
    """access_token 过期或无效。运营约定：用户去后台重新生成 token。"""


class RecordNotFoundError(StorageError):
    """指定 recordID 在表里不存在。"""


class UnknownColumnError(StorageError):
    """写入时引用了表里不存在的列名。"""


# ============================================================ binding-related


class BindingError(Exception):
    """绑定相关错误基类。"""


class MainGroupBindError(BindingError):
    """D9：总群禁止 /绑定 /解绑。"""


class AliasConflictError(BindingError):
    """D9：别名已被其他绑定占用。"""


class AliasNotFoundError(BindingError):
    """指定的番剧别名/名称没有任何绑定。"""


class AmbiguousShowError(BindingError):
    """D9：一群多番时命令省略番剧名 → 让用户选。"""

    def __init__(self, group_id: int, candidates: list[str]) -> None:
        self.group_id = group_id
        self.candidates = candidates
        super().__init__(
            f"群 {group_id} 绑定了多个番剧 {candidates}，请在命令里指明"
        )


class NotBoundError(BindingError):
    """该群一个番剧都没绑定。"""


# ============================================================ pipeline-related


class PipelineError(Exception):
    """流水线 DSL 解析或操作错误。"""
