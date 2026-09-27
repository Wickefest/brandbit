# Tests Kimi temperature policy and base URL normalization.
# Covers thinking on thinking off and moonshot host rewriting.
from src.services.llm_chat import _kimi_temperature, _normalize_kimi_base_url


def test_kimi_k2_thinking_on_forces_temperature_one():
    assert _kimi_temperature("kimi-k2.6", 0.4, thinking_disabled=False) == 1.0
    assert _kimi_temperature("kimi-k2.5", 0.1, thinking_disabled=False) == 1.0
    assert _kimi_temperature("kimi-k3", 0.2, thinking_disabled=False) == 1.0

def test_kimi_k2_thinking_off_forces_temperature_point_six():
    assert _kimi_temperature("kimi-k2.6", 0.4, thinking_disabled=True) == 0.6
    assert _kimi_temperature("kimi-k2.5", 1.0, thinking_disabled=True) == 0.6

def test_legacy_moonshot_keeps_requested_temperature():
    assert _kimi_temperature("moonshot-v1-32k", 0.4) == 0.4

def test_normalize_rewrites_moonshot_cn():
    assert _normalize_kimi_base_url("https://api.moonshot.cn/v1") == (
        "https://api.moonshot.ai/v1"
    )

def test_normalize_keeps_international_v1():
    assert _normalize_kimi_base_url("https://api.moonshot.ai/v1") == (
        "https://api.moonshot.ai/v1"
    )
