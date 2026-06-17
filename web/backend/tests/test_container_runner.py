from pathlib import Path
from app.config import Settings
from app.runners.container import ContainerRunner

def test_docker_args_security_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("WEWRITE_JOB_IMAGE", "wewrite-job:test")
    monkeypatch.setenv("WEWRITE_JOB_NETWORK", "wewrite-jobs")
    monkeypatch.setenv("WEWRITE_JOB_CPUS", "2")
    monkeypatch.setenv("WEWRITE_JOB_MEMORY", "2g")
    monkeypatch.setenv("WEWRITE_JOB_PIDS", "512")
    s = Settings()
    r = ContainerRunner(s)
    args = r._docker_args(tmp_path, {"ANTHROPIC_BASE_URL": "https://relay.upthos.com",
                                     "WEWRITE_MODEL": "claude-sonnet-4-6"})
    joined = " ".join(args)
    assert args[:3] == ["docker", "run", "--rm"]
    assert "--cap-drop" in args and "ALL" in args
    assert "--security-opt" in args and "no-new-privileges" in args
    assert "--read-only" in args
    assert "--network" in args and "wewrite-jobs" in args
    assert "--cpus" in args and "--memory" in args and "--pids-limit" in args
    assert f"{tmp_path}:/workspace" in args
    assert f"{s.skill_dir}:/skill:ro" in args
    assert "HOME=/workspace/.home" in joined
    assert "ANTHROPIC_BASE_URL=https://relay.upthos.com" in joined
    assert "WEWRITE_MODEL=claude-sonnet-4-6" in joined
    assert args[-1] == "wewrite-job:test"

def test_parse_event_line():
    r = ContainerRunner(Settings())
    assert r._parse_event_line('{"type":"assistant_text","text":"hi"}')["type"] == "assistant_text"
    assert r._parse_event_line("not json") is None
    assert r._parse_event_line("") is None
    assert r._parse_event_line('{"no_type":1}') is None
