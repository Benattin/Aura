from aura.vision import wants_screen


def test_wants_screen():
    assert wants_screen("olha a tela")
    assert wants_screen("o que tem na tela")
    assert wants_screen("me ajuda com a tela")
    assert wants_screen("tela")


def test_print_is_not_vision():
    assert not wants_screen("print da tela")
    assert not wants_screen("captura a tela")
