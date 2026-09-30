import base64
from pathlib import Path

from aura.config import ROOT
from aura.files import (
    deliver_text,
    file_query,
    from_attachment,
    from_attachment_b64,
    remove_named_file,
    wants_code,
    wants_deliver,
    wants_file_help,
    wants_remove_file,
)
from aura.workspace import wants_workspace
from aura.skills import _is_inside_project, resolve_existing


def test_wants_read():
    assert wants_file_help("leia o arquivo skills.py")
    assert wants_file_help("analise o erro em hub.py")
    assert wants_file_help("abra hub.py")
    assert wants_file_help("procure config.json")
    assert wants_file_help(r"abre D:\AURA\run.bat")
    assert wants_file_help("leia o arquivo nota.pdf")
    assert not wants_file_help("olha a tela")
    assert not wants_file_help("abra a pasta de documentos")


def test_wants_code():
    assert wants_code("escreve uma função em python que some dois números")
    assert wants_code("corrija este TypeError")
    assert not wants_code("olha a tela")


def test_wants_deliver_and_remove():
    assert wants_deliver("crie um arquivo relatorio.txt com o resumo")
    assert wants_deliver("salve um documento pdf com as notas")
    assert wants_remove_file("apague relatorio.txt")
    assert not wants_deliver("leia o arquivo hub.py")
    assert not wants_workspace("crie um arquivo relatorio.txt com o resumo")


def test_file_query():
    assert "skills.py" in file_query("leia o arquivo skills.py")
    assert file_query(r"leia C:\Users\gusta\Desktop\nota.txt").startswith("C:")
    assert "hub.py" in file_query("abra hub.py")


def test_absolute_path_and_outside_project(tmp_path):
    f = tmp_path / "fora_da_aura.py"
    f.write_text("print(1)\n")
    found = resolve_existing(str(f))
    assert found == f.resolve()
    assert not _is_inside_project(found)
    assert _is_inside_project(ROOT / "src" / "aura" / "hub.py")


def test_from_attachment_reads_text():
    result = from_attachment("nota.py", "print(1)\n")
    assert result.path.name == "nota.py"
    assert "print(1)" in result.text


def test_from_attachment_reads_image():
    result = from_attachment_b64("foto.png", base64.b64encode(b"\x89PNG\r\n\x1a\n").decode())
    assert result.kind == "image"
    assert result.image_b64


def test_deliver_and_remove(tmp_path, monkeypatch):
    monkeypatch.setattr("aura.files.output_dir", lambda: tmp_path)
    path = deliver_text("teste_entrega.txt", "conteudo")
    assert path.exists()
    assert path.read_text(encoding="utf-8") == "conteudo"
    ok, msg = remove_named_file(f"apague {path.name}")
    assert ok
    assert not path.exists()
