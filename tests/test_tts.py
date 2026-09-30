from aura.tts import take_sentences


def test_take_sentences_splits_on_period():
    done, rest = take_sentences("Sim, senhor. Vou verificar. e")
    assert done[0] == "Sim, senhor."
    assert "Vou verificar." in done
    assert rest == "e"


def test_take_sentences_keeps_incomplete():
    done, rest = take_sentences("Estou pensando")
    assert done == []
    assert rest == "Estou pensando"
