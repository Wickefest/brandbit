# Tests saving upload image bytes under the input image directory.
# Checks jpeg and png extension handling and round trip loading.
from __future__ import annotations
from pathlib import Path
from src.config import Settings
from src.services.clip_proxies import persist_input_image, resolve_image_bytes


def test_persist_input_image_round_trip(tmp_path: Path):
    settings = Settings(input_image_dir=str(tmp_path / "images"))
    jpeg = b"\xff\xd8\xff fake jpeg"
    path = persist_input_image(jpeg, "Brand_001 (BAD)", settings)
    assert Path(path).is_file()
    assert Path(path).suffix == ".jpg"
    assert resolve_image_bytes(path) == jpeg


def test_persist_input_image_png_extension(tmp_path: Path):
    settings = Settings(input_image_dir=str(tmp_path / "images"))
    png = b"\x89PNG\r\n\x1a\n" + b"payload"
    path = persist_input_image(png, "Brand_002", settings)
    assert Path(path).suffix == ".png"
