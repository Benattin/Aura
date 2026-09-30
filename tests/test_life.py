from datetime import datetime, timedelta

from aura.life import handle
from aura.memory import Memory


def test_note_and_todo(tmp_path):
    mem = Memory(tmp_path / "m.json")
    assert "Anotado" in handle("anota comprar pão", mem)
    assert "pão" in handle("minhas notas", mem)
    assert "Entrou" in handle("adiciona na lista leite", mem)
    assert "leite" in handle("minhas tarefas", mem)


def test_remember_and_help(tmp_path):
    mem = Memory(tmp_path / "m.json")
    assert "Guardei" in handle("lembre que eu trabalho de noite", mem)
    assert "noite" in handle("o que você sabe de mim", mem)
    assert "resumo do dia" in handle("ajuda", mem)


def test_calc_and_brief(tmp_path):
    mem = Memory(tmp_path / "m.json")
    assert "6" in handle("quanto é 2 mais 4", mem)
    assert "São" in handle("resumo do dia", mem)


def test_reminder_in(tmp_path):
    mem = Memory(tmp_path / "m.json")
    msg = handle("me lembre em 5 minutos de beber água", mem)
    assert msg and "água" in msg
    assert mem.reminders
    at = datetime.fromisoformat(mem.reminders[0]["at"])
    assert at > datetime.now()
    assert at < datetime.now() + timedelta(minutes=6)
