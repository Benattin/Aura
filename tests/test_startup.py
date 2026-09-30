from pathlib import Path

from aura.startup import write_vbs


def test_write_vbs_without_startup_delay(tmp_path, monkeypatch):
    vbs = tmp_path / "start-silent.vbs"
    launcher = tmp_path / "scripts" / "launch-aura.bat"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("@echo off\n", encoding="utf-8")
    monkeypatch.setattr("aura.startup.ROOT", tmp_path)
    monkeypatch.setattr("aura.startup.VBS", vbs)
    write_vbs()
    text = vbs.read_text(encoding="utf-8")
    assert "AURA_STARTUP" not in text
    assert "launch-aura.bat" in text
