from aura.config import load_settings
from aura.token_stress import (
    check_large_context,
    check_session_history,
    check_unlimited_predict,
)

import pytest


@pytest.mark.slow
def test_session_keeps_large_history():
    s = load_settings()
    ctx = s.num_ctx if s.num_ctx > 0 else 8192
    r = check_session_history(ctx)
    assert r.ok, r.detail


@pytest.mark.slow
def test_ollama_unlimited_predict():
    r = check_unlimited_predict()
    assert r.ok, r.detail


@pytest.mark.slow
def test_ollama_large_context():
    r = check_large_context()
    assert r.ok, r.detail
