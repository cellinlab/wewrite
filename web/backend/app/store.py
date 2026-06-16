"""账户与任务的存储 + 任务事件总线。

NOTE(生产): 这是进程内存版，便于本地起步与演示。生产应替换为数据库：
  - 账户（含加密后的微信凭证、风格偏好）
  - 任务记录与产物（文章 markdown、预览 HTML、草稿状态）
事件流可改用 Redis pub/sub 以支持多副本水平扩展。
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class PlatformLogin:
    """某平台的登录态（cookie 加密存储）。

    NOTE(多租户): cookie_enc 是按用户加密存放登录态的位置。参考实现 xiaohongshu-mcp
    是单账号、cookie 存服务端的；要真正按用户隔离，需为每用户起独立 MCP 实例并把这里的
    cookie 注入。logged_in 记录最近一次探测到的登录状态。
    """

    logged_in: bool = False
    user_name: str = ""
    cookie_enc: Optional[str] = None
    updated_at: float = 0.0


@dataclass
class Account:
    user_id: str
    account_name: str = ""
    writing_persona: str = "midnight-friend"
    theme: str = "professional-clean"
    audience: str = ""
    tone: str = ""
    # 加密后的微信凭证（密文）
    wechat_appid_enc: Optional[str] = None
    wechat_secret_enc: Optional[str] = None
    wechat_author: str = ""
    # 各平台登录态（小红书等）
    platform_login: dict[str, PlatformLogin] = field(default_factory=dict)

    @property
    def wechat_bound(self) -> bool:
        return bool(self.wechat_appid_enc and self.wechat_secret_enc)

    def login(self, platform: str) -> PlatformLogin:
        return self.platform_login.setdefault(platform, PlatformLogin())


@dataclass
class Job:
    id: str
    user_id: str
    prompt: str
    interactive: bool = False
    theme: Optional[str] = None
    persona: Optional[str] = None
    publish_draft: bool = False
    status: str = "queued"  # queued | running | done | error
    created_at: float = field(default_factory=time.time)
    completion: Optional[str] = None  # DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT
    error: Optional[str] = None
    # 产物
    article_markdown: Optional[str] = None
    preview_html: Optional[str] = None
    title: Optional[str] = None
    images: list[str] = field(default_factory=list)  # 服务 URL（前端预览 / 发布）
    image_paths: list[str] = field(default_factory=list)  # 持久化后的绝对磁盘路径（供本机 MCP 读取）
    # 事件流
    events: list[dict[str, Any]] = field(default_factory=list)
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    _done: asyncio.Event = field(default_factory=asyncio.Event)

    def emit(self, event: dict[str, Any]) -> None:
        event = {"seq": len(self.events), "ts": time.time(), **event}
        self.events.append(event)
        self._queue.put_nowait(event)

    def finish(self) -> None:
        self._done.set()
        self._queue.put_nowait(None)  # 哨兵，结束 SSE


class Store:
    def __init__(self) -> None:
        self._accounts: dict[str, Account] = {}
        self._jobs: dict[str, Job] = {}

    # ---- 账户 ----
    def account(self, user_id: str) -> Account:
        return self._accounts.setdefault(user_id, Account(user_id=user_id))

    # ---- 任务 ----
    def create_job(self, **kwargs: Any) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], **kwargs)
        self._jobs[job.id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_jobs(self, user_id: str) -> list[Job]:
        return sorted(
            (j for j in self._jobs.values() if j.user_id == user_id),
            key=lambda j: j.created_at,
            reverse=True,
        )


STORE = Store()
