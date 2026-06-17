"""llm_write 工具单测：配置门、摘要-不回正文、去代码围栏。真网络调用在服务器/容器内验证。"""
import json
from pathlib import Path

import pytest

import llm_write  # conftest 把 repo/scripts 加进了 sys.path


def test_not_configured_exits_3(monkeypatch, tmp_path):
    monkeypatch.delenv("WEWRITE_WRITER_API_KEY", raising=False)
    (tmp_path / "b.md").write_text("brief", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        llm_write.main(["--brief", str(tmp_path / "b.md"), "--output", str(tmp_path / "o.md")])
    assert e.value.code == 3


def test_writes_file_and_prints_summary_only(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("WEWRITE_WRITER_API_KEY", "sk-test")
    monkeypatch.setenv("WEWRITE_WRITER_MODEL", "deepseek-chat")
    (tmp_path / "b.md").write_text("写一篇关于 X 的文章", encoding="utf-8")
    out = tmp_path / "art.md"

    body = "# 真人标题\n\n正文内容一大段，绝不该出现在 stdout 里。"
    monkeypatch.setattr(llm_write, "call_writer",
                        lambda cfg, system, user: (body, {"prompt_tokens": 12, "completion_tokens": 345}))

    llm_write.main(["--brief", str(tmp_path / "b.md"), "--output", str(out)])

    # 正文写进文件
    assert out.read_text(encoding="utf-8").startswith("# 真人标题")
    # stdout 只有摘要 JSON，且不含正文
    cap = capsys.readouterr().out.strip()
    summary = json.loads(cap)
    assert summary["ok"] is True and summary["output"] == str(out)
    assert summary["tokens_out"] == 345 and summary["model"] == "deepseek-chat"
    assert "正文内容" not in cap  # 省钱命门：正文不回灌


def test_strips_code_fence(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("WEWRITE_WRITER_API_KEY", "sk-test")
    (tmp_path / "b.md").write_text("x", encoding="utf-8")
    out = tmp_path / "art.md"
    monkeypatch.setattr(llm_write, "call_writer",
                        lambda *a: ("```markdown\n# 标题\n正文\n```", {}))
    llm_write.main(["--brief", str(tmp_path / "b.md"), "--output", str(out)])
    text = out.read_text(encoding="utf-8")
    assert "```" not in text and text.startswith("# 标题")
