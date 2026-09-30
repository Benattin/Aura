from aura.skills import dispatch


def test_open_edge(monkeypatch):
    called = []
    monkeypatch.setattr("aura.skills._start", lambda *a: called.append(a))
    msg = dispatch("Abra o Edge")
    assert called == [("msedge",)]
    assert "edge" in msg.lower()


def test_web_search(monkeypatch):
    urls = []
    monkeypatch.setattr("aura.skills.webbrowser.open", lambda u: urls.append(u))
    msg = dispatch("pesquise por receita de bolo")
    assert urls and "bing.com/search" in urls[0]
    assert "receita" in msg.lower()


def test_youtube(monkeypatch):
    urls = []
    monkeypatch.setattr("aura.skills.webbrowser.open", lambda u: urls.append(u))
    dispatch("abra o youtube")
    assert urls[0] == "https://www.youtube.com"


def test_find_files_asks_when_empty():
    assert "Qual arquivo" in dispatch("procure o arquivo a")


def test_chat_skips_skills():
    assert dispatch("qual é a capital da frança") is None


def test_volume_up(monkeypatch):
    taps = []
    monkeypatch.setattr("aura.skills._tap", lambda vk: taps.append(vk))
    dispatch("aumenta o volume")
    assert len(taps) == 4
