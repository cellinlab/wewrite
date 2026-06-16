"""WeWrite Web 后端入口。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routes import account, catalog, jobs, publish

app = FastAPI(title="WeWrite Web", version="0.1.0")

settings = get_settings()
# 生成的图片产物（公开可取，供 <img> 与发布渠道读取）。
# NOTE(生产): 换对象存储 + CDN；如需鉴权改为签名 URL。
settings.artifact_root.mkdir(parents=True, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=str(settings.artifact_root)), name="artifacts")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(account.router)
app.include_router(jobs.router)
app.include_router(publish.router)


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "ok": True,
        "model": s.model,
        "llm_key_configured": bool(s.anthropic_api_key),
        "image_pool_configured": bool(s.image_config()),
        "skill_dir": str(s.skill_dir),
    }
