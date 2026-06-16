"""多平台发布：列出平台 / 扫码登录 / 登录状态 / 发布。"""
from __future__ import annotations

import re
import time

from fastapi import APIRouter, Depends, HTTPException

from ..config import get_settings
from ..models import (
    LoginChallengeResp,
    LoginStatusResp,
    PlatformStatus,
    PublishRequest,
    PublishResponse,
)
from ..publisher.base import NotePayload
from ..publisher.registry import get_publisher, list_platforms
from ..store import STORE
from . import current_user

router = APIRouter(prefix="/api/publish", tags=["publish"])


def _publisher(platform: str, user_id: str):
    settings = get_settings()
    account = STORE.account(user_id)
    try:
        return get_publisher(platform, settings, account), account
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/platforms", response_model=list[PlatformStatus])
def platforms(user_id: str = Depends(current_user)) -> list[PlatformStatus]:
    settings = get_settings()
    account = STORE.account(user_id)
    out: list[PlatformStatus] = []
    for info in list_platforms(settings):
        login = account.platform_login.get(info.id)
        logged_in = account.wechat_bound if info.id == "wechat" else bool(login and login.logged_in)
        out.append(
            PlatformStatus(
                id=info.id,
                label=info.label,
                login_kind=info.login_kind.value,
                supports_text=info.supports_text,
                supports_image=info.supports_image,
                supports_video=info.supports_video,
                available=info.available,
                note=info.note,
                logged_in=logged_in,
                user_name=(account.wechat_author if info.id == "wechat" else (login.user_name if login else "")),
            )
        )
    return out


@router.post("/{platform}/login/start", response_model=LoginChallengeResp)
def login_start(platform: str, user_id: str = Depends(current_user)) -> LoginChallengeResp:
    pub, _ = _publisher(platform, user_id)
    try:
        ch = pub.start_login()
    except NotImplementedError:
        raise HTTPException(status_code=400, detail=f"{platform} 不支持扫码登录")
    except Exception as exc:  # noqa: BLE001 - MCP/网络错误回传前端
        raise HTTPException(status_code=502, detail=f"发起登录失败：{exc}") from exc
    return LoginChallengeResp(
        kind=ch.kind.value, qrcode_image=ch.qrcode_image,
        challenge_id=ch.challenge_id, detail=ch.detail,
    )


@router.get("/{platform}/status", response_model=LoginStatusResp)
def login_status(platform: str, user_id: str = Depends(current_user)) -> LoginStatusResp:
    pub, account = _publisher(platform, user_id)
    try:
        st = pub.login_status()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"查询登录状态失败：{exc}") from exc
    if platform != "wechat":
        login = account.login(platform)
        login.logged_in = st.logged_in
        login.user_name = st.user_name
        login.updated_at = time.time()
    return LoginStatusResp(logged_in=st.logged_in, detail=st.detail, user_name=st.user_name)


@router.delete("/{platform}/login", response_model=LoginStatusResp)
def logout(platform: str, user_id: str = Depends(current_user)) -> LoginStatusResp:
    pub, account = _publisher(platform, user_id)
    try:
        pub.logout()
    except Exception:  # noqa: BLE001 - 登出失败不阻断本地清理
        pass
    account.platform_login.pop(platform, None)
    return LoginStatusResp(logged_in=False, detail="已登出")


@router.post("/{platform}", response_model=PublishResponse)
def publish(platform: str, req: PublishRequest, user_id: str = Depends(current_user)) -> PublishResponse:
    pub, _ = _publisher(platform, user_id)
    note = _build_note(req, user_id)

    # 非微信渠道：发布前确认已登录
    if platform != "wechat":
        try:
            st = pub.login_status()
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=f"查询登录状态失败：{exc}") from exc
        if not st.logged_in:
            raise HTTPException(status_code=409, detail="尚未登录该平台，请先扫码登录。")

    try:
        result = pub.publish(note)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"发布失败：{exc}") from exc
    return PublishResponse(ok=result.ok, platform=result.platform, url=result.url, detail=result.detail)


def _build_note(req: PublishRequest, user_id: str) -> NotePayload:
    if req.note is not None:
        n = req.note
        return NotePayload(title=n.title, content=n.content, images=n.images, tags=n.tags, video=n.video)
    if req.job_id:
        job = STORE.get_job(req.job_id)
        if not job or job.user_id != user_id:
            raise HTTPException(status_code=404, detail="任务不存在")
        return NotePayload(
            title=job.title or "未命名",
            content=_markdown_to_plain(job.article_markdown or ""),
            images=list(job.image_paths),  # 持久化后的本机绝对路径，供本机 MCP 读取
        )
    raise HTTPException(status_code=400, detail="需提供 note 或 job_id")


def _markdown_to_plain(md: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)  # 图片整体去掉
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)  # 标题井号
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # 链接保留文字
    text = re.sub(r"[*`>]", "", text)  # 粗体/代码/引用标记
    return text.strip()
