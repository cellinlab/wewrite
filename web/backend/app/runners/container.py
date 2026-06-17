"""容器 runner：每任务起一个一次性硬化 Docker 容器跑管道。

事件走容器 stdout 的 JSONL；产物走挂载的工作区。线上用，凭证走 relay（env 注入）。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ..config import Settings
from ..job_spec import JobSpec
from ..pipeline import Emit


class ContainerRunner:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _docker_args(self, ws: Path, env: dict) -> list[str]:
        s = self._settings
        args = [
            "docker", "run", "--rm", "-i",
            "--network", s.job_network,
            "--cpus", str(s.job_cpus),
            "--memory", s.job_memory,
            "--pids-limit", str(s.job_pids),
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--read-only",
            "--tmpfs", "/tmp",
            "-e", "HOME=/workspace/.home",
            "-v", f"{ws}:/workspace",
            "-v", f"{s.skill_dir}:/skill:ro",
            "-w", "/workspace",
        ]
        for k, v in env.items():
            args += ["-e", f"{k}={v}"]
        args.append(s.job_image)
        return args

    @staticmethod
    def _parse_event_line(line: str) -> dict | None:
        line = line.strip()
        if not line:
            return None
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            return None
        if isinstance(obj, dict) and "type" in obj:
            return obj
        return None

    async def run(self, *, settings: Settings, spec: JobSpec, profiles: list,
                  ws: Path, env: dict, emit: Emit) -> None:
        # 写任务规格供容器入口读取
        (ws / "job-spec.json").write_text(
            json.dumps(spec.to_dict(), ensure_ascii=False), encoding="utf-8")

        args = self._docker_args(ws, env)
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)

        async def pump() -> None:
            assert proc.stdout is not None
            async for raw in proc.stdout:
                ev = self._parse_event_line(raw.decode("utf-8", "replace"))
                if ev is not None:
                    emit(ev)

        try:
            await asyncio.wait_for(pump(), timeout=settings.job_timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(f"任务容器超时（>{settings.job_timeout:.0f}s），已终止")

        rc = await proc.wait()
        if rc != 0:
            err = b""
            if proc.stderr is not None:
                err = await proc.stderr.read()
            tail = err.decode("utf-8", "replace").strip()[-500:]
            raise RuntimeError(f"任务容器非零退出（code={rc}）：{tail}")
