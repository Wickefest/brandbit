# Tests the FastAPI generate and health endpoints with mocked pipeline runs.
# Covers format rejection streaming and successful generate responses.
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.models.congruence import (
    AutomatedProxySignals,
    CongruenceReport,
    DescriptorConsistency,
)


@pytest.fixture
def client():
    return TestClient(app)

def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_generate_rejects_unsupported_format(client):
    response = client.post(
        "/api/generate",
        files={"image": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert "Unsupported format" in response.json()["detail"]

def test_generate_happy_path_with_mocked_pipeline(
    client,
    sample_visual,
    sample_bad,
    sample_fragrance,
    sample_music,
    monkeypatch,
):
    monkeypatch.setattr("src.main.analyse_image", lambda _data: sample_visual)
    monkeypatch.setattr(
        "src.main.generate_descriptor",
        lambda _visual, brand_item=None: sample_bad,
    )
    monkeypatch.setattr(
        "src.main.persist_input_image",
        lambda image_bytes, execution_id, settings=None: f"/tmp/{execution_id}.jpg",
    )
    monkeypatch.setattr(
        "src.main.run_specialist_congruence_loop",
        lambda _bad, execution_id=None, image_data=None, verbose=False, **_kw: (
            sample_fragrance,
            sample_music.model_copy(
                update={"audio_sample_ref": f"/api/audio/{execution_id}" if execution_id else None}
            ),
            CongruenceReport(
                automated_proxies=AutomatedProxySignals(),
                descriptor_consistency=DescriptorConsistency(
                    fragrance_aligns_descriptor=True,
                    music_aligns_descriptor=True,
                    details="aligned",
                ),
                summary="Congruent overall",
                accepted=True,
                regen_count=0,
            ),
        ),
    )
    monkeypatch.setattr(
        "src.main.generate_rationale",
        lambda *_a, **_k: "## Visual to Descriptor\nok\n## Descriptor to Fragrance\nokk\n## Descriptor to Music\nokkk",
    )
    monkeypatch.setattr("src.main.log_execution", lambda _record: "eval/result/mock.json")

    response = client.post(
        "/api/generate",
        files={"image": ("brand.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        data={"brand_item": "linen bottle"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "execution_id" in body
    assert body["brand_aesthetic_descriptor"]["brand_item"] == sample_bad.brand_item
    assert body["fragrance_concept"]["top_notes"] == sample_fragrance.top_notes
    assert body["music_direction"]["style"] == sample_music.style
    assert body["audio_sample_ref"] == body["music_direction"]["audio_sample_ref"]
    assert body["congruence_report"]["summary"] == "Congruent overall"
    assert body["congruence_report"]["accepted"] is True
    assert body["congruence_accepted"] is True
    assert body["refinement_history"] == []
    assert body["rationale"].startswith("## Visual to Descriptor")
    assert body.get("mode") == "sensory_profile"
    assert body["execution_id"].endswith(" (BAD)")
    assert "log_path" not in body

def test_generate_prompt_mode_skips_bad_llm(
    client,
    sample_visual,
    sample_fragrance,
    sample_music,
    monkeypatch,
):
    called = {"bad": 0}

    def _fake_bad(*_a, **_k):
        called["bad"] += 1
        raise AssertionError("BAD LLM must not run in prompt mode")

    monkeypatch.setattr("src.main.analyse_image", lambda _data: sample_visual)
    monkeypatch.setattr("src.main.generate_descriptor", _fake_bad)
    monkeypatch.setattr(
        "src.main.persist_input_image",
        lambda image_bytes, execution_id, settings=None: f"/tmp/{execution_id}.jpg",
    )
    monkeypatch.setattr(
        "src.main.run_specialist_congruence_loop",
        lambda bad, execution_id=None, image_data=None, verbose=False, **_kw: (
            sample_fragrance,
            sample_music.model_copy(
                update={
                    "audio_sample_ref": (
                        f"/api/audio/{execution_id}" if execution_id else None
                    )
                }
            ),
            CongruenceReport(
                automated_proxies=AutomatedProxySignals(),
                descriptor_consistency=DescriptorConsistency(
                    fragrance_aligns_descriptor=True,
                    music_aligns_descriptor=True,
                    details="aligned",
                ),
                summary="Congruent overall",
                accepted=True,
                regen_count=0,
            ),
        ),
    )
    monkeypatch.setattr(
        "src.main.generate_rationale",
        lambda *_a, **_k: "## Visual to Descriptor\nok\n## Descriptor to Fragrance\nokk\n## Descriptor to Music\nokkk",
    )
    monkeypatch.setattr("src.main.log_execution", lambda _record: "eval/result/mock.json")

    response = client.post(
        "/api/generate",
        files={"image": ("brand.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        data={"mode": "prompt"},
    )

    assert response.status_code == 200
    body = response.json()
    assert called["bad"] == 0
    assert body["mode"] == "prompt_only"
    assert body["execution_id"].endswith(" (Prompt Only)")
    assert body["brand_aesthetic_descriptor"]["brand_item"] == sample_visual.primary_subject
    assert "log_path" not in body

def test_generate_rejects_invalid_mode(client):
    response = client.post(
        "/api/generate",
        files={"image": ("brand.jpg", b"fake-jpeg-bytes", "image/jpeg")},
        data={"mode": "nope"},
    )
    assert response.status_code == 400
    assert "Invalid pipeline mode" in response.json()["detail"]