from aura.reasoning import needs_reasoning


def test_needs_reasoning_questions():
    assert needs_reasoning("por que o Python usa indentação?")
    assert needs_reasoning("explique como funciona um banco de dados relacional")
    assert needs_reasoning("qual é a melhor forma de organizar um projeto web grande?")


def test_needs_reasoning_projects():
    msg = "quero que voce faça um projeto de um site, com tema de estoque inteligente"
    assert needs_reasoning(msg)


def test_skips_short_commands():
    assert not needs_reasoning("oi")
    assert not needs_reasoning("abre o youtube")
    assert not needs_reasoning("volume mais")
