from pathlib import Path

import pytest

from aura.workspace import (
    active_project,
    apply_workspace,
    create_folder,
    create_project,
    extract_files_from_llm,
    list_files,
    list_projects,
    parse_request,
    set_active_project,
    wants_workspace,
    write_file,
    workspace_dir,
)


@pytest.fixture
def ws_root(tmp_path, monkeypatch):
    monkeypatch.setattr("aura.workspace.workspace_dir", lambda: tmp_path)
    return tmp_path


def test_wants_workspace_site():
    msg = "quero que voce faça um projeto de um site, com tema de estoque inteligente"
    assert wants_workspace(msg)
    req = parse_request(msg)
    assert req
    assert req.project == "estoque-inteligente"


def test_music_skill_ignores_estoque():
    from aura.skills import dispatch

    msg = "quero que voce faça um projeto de um site, com tema de estoque inteligente"
    assert dispatch(msg) is None
    assert wants_workspace("crie um projeto calculadora na aura")
    assert wants_workspace("crie a pasta api no workspace")
    assert wants_workspace("liste os projetos da aura")
    assert wants_workspace("salve o arquivo main.py no projeto todo")
    assert not wants_workspace("olha a tela")
    assert not wants_workspace("escreve uma função python que soma dois números")


def test_parse_request():
    req = parse_request("crie um projeto hello-world")
    assert req
    assert req.project == "hello-world"
    assert req.folder_only

    req = parse_request("crie main.py no projeto api")
    assert req
    assert req.project == "api"
    assert "main.py" in req.files

    req = parse_request("liste os projetos da aura")
    assert req
    assert req.list_only


def test_create_project_and_files(ws_root):
    path = create_project("meu-app")
    assert path == ws_root / "meu-app"
    assert path.is_dir()

    sub = create_folder("meu-app", "src/utils")
    assert sub == ws_root / "meu-app" / "src" / "utils"
    assert sub.is_dir()

    fpath = write_file("meu-app", "src/main.py", "print('oi')\n")
    write_file("meu-app", "src/utils/helpers.py", "# helpers\n")
    assert fpath.read_text(encoding="utf-8") == "print('oi')\n"
    assert list_projects() == ["meu-app"]
    assert list_files("meu-app") == ["src/main.py", "src/utils/helpers.py"]


def test_path_traversal_blocked(ws_root):
    create_project("safe")
    with pytest.raises(ValueError):
        write_file("safe", "../escape.py", "x")
    with pytest.raises(ValueError):
        write_file("safe", "../../outside.py", "x")


def test_extract_files_from_llm():
    raw = (
        "### FILE: src/app.py\n"
        "```python\n"
        "def main():\n"
        "    print('ok')\n"
        "```\n"
        "### FILE: README.md\n"
        "```markdown\n"
        "# App\n"
        "```"
    )
    files = extract_files_from_llm(raw)
    assert set(files) == {"src/app.py", "README.md"}
    assert "def main()" in files["src/app.py"]


def test_apply_workspace_folder_only(ws_root):
    ok, msg = apply_workspace("crie um projeto demo", "")
    assert ok
    assert (ws_root / "demo").is_dir()
    assert "demo" in msg
    assert active_project() == "demo"


def test_active_project_persists(ws_root):
    create_project("alpha")
    set_active_project("alpha")
    create_project("beta")
    assert active_project() == "alpha"
    set_active_project("beta")
    assert active_project() == "beta"


def test_apply_workspace_with_llm_output(ws_root):
    llm = (
        "### FILE: main.py\n"
        "```python\n"
        "print(42)\n"
        "```"
    )
    ok, msg = apply_workspace("crie o projeto answers com main.py na aura", llm)
    assert ok
    assert (ws_root / "answers" / "main.py").read_text(encoding="utf-8").strip() == "print(42)"
    assert "answers" in msg


def test_apply_workspace_list(ws_root):
    create_project("alpha")
    create_project("beta")
    ok, msg = apply_workspace("liste os projetos da aura", "")
    assert ok
    assert "alpha" in msg
    assert "beta" in msg
