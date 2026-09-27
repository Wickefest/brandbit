# Tests CLIP caption building truncation backend choice and scoring helpers.
# Stays offline except where local math helpers are exercised.
from __future__ import annotations
from pathlib import Path
from src.config import Settings
from src.services import clip_proxies



def test_fragrance_and_music_captions(sample_fragrance, sample_music):
    frag = clip_proxies.fragrance_caption(sample_fragrance)
    music = clip_proxies.music_caption(sample_music)
    assert "floral" in frag.lower()
    assert len(frag) <= clip_proxies._CLIP_MAX_CHARS
    assert "ambient" in music.lower() or "music" in music.lower()
    assert "slow" in music.lower()
    assert len(music) <= clip_proxies._CLIP_MAX_CHARS
                                                                
    assert "linen-lined" not in music.lower()

def test_clip_truncate_keeps_short_text():
    assert clip_proxies._clip_truncate("short caption") == "short caption"
    long = "word " * 80
    out = clip_proxies._clip_truncate(long)
    assert len(out) <= clip_proxies._CLIP_MAX_CHARS
    assert out.endswith("…")

def test_resolve_image_bytes_from_path(tmp_path: Path):
    img = tmp_path / "brand.jpg"
    img.write_bytes(b"\xff\xd8\xff fake jpeg")
    assert clip_proxies.resolve_image_bytes(str(img)) == b"\xff\xd8\xff fake jpeg"

def test_compute_clip_proxies_off_returns_nulls(sample_fragrance, sample_music):
    settings = Settings(clip_backend="off")
    proxies = clip_proxies.compute_clip_proxies(
        b"fake",
        sample_fragrance,
        sample_music,
        settings=settings,
    )
    assert proxies.clip_score_image_fragrance_text is None
    assert proxies.clip_score_image_music_text is None

def test_compute_clip_proxies_local_mocked(
    sample_fragrance, sample_music, monkeypatch, tmp_path: Path
):
    img = tmp_path / "brand.png"
                           
    from PIL import Image

    Image.new("RGB", (1, 1), color=(10, 20, 30)).save(img)

    monkeypatch.setattr(clip_proxies, "resolve_clip_backend", lambda _s: "local")
    monkeypatch.setattr(
        clip_proxies, "_similarity", lambda _b, text, _s: 0.8 if "ambient" in text else 0.6
    )

    proxies = clip_proxies.compute_clip_proxies(
        img.read_bytes(),
        sample_fragrance,
        sample_music,
        settings=Settings(clip_backend="local"),
    )
    assert proxies.clip_score_image_fragrance_text == 0.6
    assert proxies.clip_score_image_music_text == 0.8

def test_resolve_clip_backend_auto_prefers_replicate(monkeypatch):
    settings = Settings(clip_backend="auto", musicgen_api_key="r8_test")
    assert clip_proxies.resolve_clip_backend(settings) == "replicate"

def test_compute_clip_proxies_replicate_mocked(
    sample_fragrance, sample_music, monkeypatch, tmp_path: Path
):
    img = tmp_path / "brand.png"
    from PIL import Image

    Image.new("RGB", (1, 1), color=(10, 20, 30)).save(img)

    def _fake_replicate(settings, *, text=None, image_bytes=None):
        if image_bytes is not None:
            return [1.0, 0.0]
        if text and "ambient" in text:
            return [0.8, 0.6]
        return [0.6, 0.8]

    monkeypatch.setattr(clip_proxies, "_replicate_embedding", _fake_replicate)
    proxies = clip_proxies.compute_clip_proxies(
        img.read_bytes(),
        sample_fragrance,
        sample_music,
        settings=Settings(clip_backend="replicate", musicgen_api_key="r8_test"),
    )
    assert proxies.clip_score_image_fragrance_text is not None
    assert proxies.clip_score_image_music_text is not None

def test_congruence_loop_attaches_clip_proxies(
    sample_bad, sample_fragrance, sample_music, monkeypatch
):
    from src.models.congruence import (
        AutomatedProxySignals,
        CongruenceReport,
        DescriptorConsistency,
    )
    from src.services import congruence_scoring

    monkeypatch.setattr(
        congruence_scoring,
        "_get_settings",
        lambda: Settings(congruence_regen_max_retries=0, clip_backend="off"),
    )
    monkeypatch.setattr(
        "src.services.fragrance_generation.generate_fragrance",
        lambda bad, judge_feedback=None: sample_fragrance,
    )
    monkeypatch.setattr(
        "src.services.music_generation.generate_music_direction",
        lambda bad, judge_feedback=None: sample_music,
    )
    monkeypatch.setattr(
        congruence_scoring,
        "compute_congruence",
        lambda *_a, **_k: CongruenceReport(
            automated_proxies=AutomatedProxySignals(),
            descriptor_consistency=DescriptorConsistency(
                fragrance_aligns_descriptor=True,
                music_aligns_descriptor=True,
                details="ok",
            ),
            summary="aligned",
            accepted=True,
        ),
    )
    monkeypatch.setattr(
        "src.services.clip_proxies.compute_clip_proxies",
        lambda *_a, **_k: AutomatedProxySignals(
            clip_score_image_fragrance_text=0.72,
            clip_score_image_music_text=0.68,
        ),
    )

    _fragrance, _music, report = congruence_scoring.run_specialist_congruence_loop(
        sample_bad,
        image_data=b"fake-image",
    )
    assert report.automated_proxies.clip_score_image_fragrance_text == 0.72
    assert report.automated_proxies.clip_score_image_music_text == 0.68
