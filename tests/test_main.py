from aura.__main__ import _pids_on_port


def test_pids_on_port_parses_netstat():
    pids = _pids_on_port(8765)
    assert isinstance(pids, list)
    assert all(isinstance(pid, int) and pid > 0 for pid in pids)
