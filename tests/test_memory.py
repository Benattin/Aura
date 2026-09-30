from aura.memory import Memory, wants_forget


def test_learns_like(tmp_path):
    mem = Memory(tmp_path / "m.json")
    mem.observe("eu gosto de lo-fi")
    assert any("lo-fi" in x.lower() for x in mem.likes)
    assert "Gosta" in mem.render()


def test_forget(tmp_path):
    mem = Memory(tmp_path / "m.json")
    mem.observe("eu gosto de café")
    assert wants_forget("esqueça o que sabe")
    mem.observe("esqueça o que sabe")
    assert mem.count() == 0


def test_notes_and_chats_persist(tmp_path):
    p = tmp_path / "m.json"
    mem = Memory(p)
    mem.add_note("comprar café")
    cid = mem.new_chat()
    mem.write_chat(cid, [{"role": "user", "content": "olá"}, {"role": "assistant", "content": "oi"}])
    mem2 = Memory(p)
    assert any("café" in (n.get("text") or "") for n in mem2.notes)
    assert "Notas" in mem2.render()
    assert mem2.chats_index()
    assert mem2.other_chats("x")
