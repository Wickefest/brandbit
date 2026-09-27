# Tests the FastAPI refine endpoint with a mocked refinement service.
# Covers not found clarification and successful refine responses.
from __future__ import annotations
from fastapi.testclient import TestClient
from src.main import app
from src.models.congruence import (
    AutomatedProxySignals,
    CongruenceReport,
    DescriptorConsistency,
)


def test_refine_not_found(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(
        "src.main.run_refinement",
        lambda *_a, **_k: (_ for _ in ()).throw(LookupError("Execution not found: x")),
    )
    response = client.post(
        "/api/refine",
        data={"execution_id": "x", "feedback": "warmer"},
    )
    assert response.status_code == 404

def test_refine_clarification(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(
        "src.main.run_refinement",
        lambda *_a, **_k: {
            "success": False,
            "execution_id": "Aqua_001",
            "clarification_request": "Which modality?",
        },
    )
    response = client.post(
        "/api/refine",
        data={"execution_id": "Aqua_001", "feedback": "change it"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "modality" in body["clarification_request"].lower()

def test_refine_happy_path(sample_bad, sample_fragrance, sample_music, monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(
        "src.main.run_refinement",
        lambda execution_id, feedback: {
            "success": True,
            "execution_id": execution_id,
            "brand_aesthetic_descriptor": sample_bad.model_dump(mode="json"),
            "fragrance_concept": sample_fragrance.model_dump(mode="json"),
            "music_direction": sample_music.model_dump(mode="json"),
            "audio_sample_ref": f"/api/audio/{execution_id}",
            "rationale": "## Visual to Descriptor\nok",
            "congruence_report": CongruenceReport(
                automated_proxies=AutomatedProxySignals(),
                descriptor_consistency=DescriptorConsistency(
                    fragrance_aligns_descriptor=True,
                    music_aligns_descriptor=True,
                    details="ok",
                ),
                summary="aligned",
                accepted=True,
            ).model_dump(mode="json"),
            "refinement_history": [
                {"feedback": feedback, "changed_fields": ["energy"]}
            ],
            "refinement": {
                "changed_fields": ["energy"],
                "change_reason": "higher energy",
                "target_modality": "music",
            },
            "log_path": "eval/result/mock.json",
        },
    )
    response = client.post(
        "/api/refine",
        data={"execution_id": "Aqua_001", "feedback": "more energetic"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["execution_id"] == "Aqua_001"
    assert "log_path" not in body
    assert body["refinement"]["changed_fields"] == ["energy"]
    assert len(body["refinement_history"]) == 1
