"""FFmpeg assembly (silicare/assemble.py) on synthetic footage."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from silicare import assemble, common

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg не установлен")

REEL_ID = "reel-07-asmr"  # 15 s, 5 shots, one shot without titles


def make_footage(root: Path) -> Path:
    folder = root / REEL_ID
    folder.mkdir(parents=True)
    # Landscape clip with sound: exercises crop-to-fill and the clip's own audio.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=4",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-shortest",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(folder / "shot-01.mp4")],
        check=True,
    )
    # A still for shot 3: exercises the slow push-in.
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=600x800", "-frames:v", "1",
         str(folder / "shot-03.png")],
        check=True,
    )
    return root


def test_missing_footage_is_an_error_without_preview(tmp_path):
    footage = make_footage(tmp_path / "footage")
    with pytest.raises(assemble.AssembleError, match="нет исходников"):
        assemble.assemble(REEL_ID, "ru", footage_root=footage, out_dir=tmp_path / "out", preset="ultrafast")


def test_preview_render_matches_delivery_spec(tmp_path):
    footage = make_footage(tmp_path / "footage")
    out = assemble.assemble(REEL_ID, "ru", footage_root=footage, out_dir=tmp_path / "out",
                            preview=True, preset="ultrafast")
    assert out.name == f"{REEL_ID}.ru.preview.mp4"
    style = common.style()
    info = assemble.verify(out, style, 15)
    assert (info["width"], info["height"]) == (1080, 1920)
    assert info["fps"] == pytest.approx(24)


def test_uzbek_titles_need_a_font_with_uzbek_letters(tmp_path):
    pytest.importorskip("fontTools")
    footage = make_footage(tmp_path / "footage")
    with pytest.raises(assemble.AssembleError, match="не содержит"):
        assemble.assemble("reel-01-how-to-apply", "uz", footage_root=footage, out_dir=tmp_path / "out",
                          preview=True, preset="ultrafast")


def test_safe_zone_guard():
    style = common.style()
    style["titles"] = {**style["titles"], "bottom_margin_px": 100}
    with pytest.raises(assemble.AssembleError, match="безопасной зоны"):
        assemble.check_safe_zone(style)
