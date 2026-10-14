"""Animated Reels 4: Remotion sources, sound bed, and assembly from one full render."""

from __future__ import annotations

import re
import shutil
import subprocess

import numpy as np
import pytest

from silicare import assemble, common, soundbed

REEL = common.load_json(common.ROOT / "reels" / "reel-04-why-scar-gets-rough.json")
SRC = common.ROOT / "remotion" / REEL["remotion"]["dir"]


def _const(name: str) -> int:
    m = re.search(rf"export const {name} = (\d+);", (SRC / "geometry.ts").read_text(encoding="utf-8"))
    assert m, name
    return int(m.group(1))


def test_composition_matches_the_scenario():
    style = common.style()
    assert _const("W") == style["video"]["width"] and _const("H") == style["video"]["height"]
    assert _const("FPS") == style["video"]["fps"]
    assert _const("DURATION") == REEL["length_sec"] * style["video"]["fps"]
    assert f'id="{REEL["remotion"]["composition_id"]}"' in (SRC / "Root.tsx").read_text(encoding="utf-8")
    assert (SRC / "art-direction.md").exists()


def test_atelier_sources_do_not_reuse_stock_components():
    for path in SRC.glob("*.ts*"):
        text = path.read_text(encoding="utf-8")
        imports = re.findall(r"""from\s+["']([^"']+)["']""", text)
        for name in imports:
            assert name in {"react", "remotion"} or name.startswith("./"), f"{path.name}: {name}"
        assert "Math.random" not in text and "Date.now" not in text, path.name


def test_soundbed_follows_the_shots():
    audio = soundbed.reel04(REEL["length_sec"])
    assert audio.shape == (REEL["length_sec"] * soundbed.SR, 2)
    assert np.abs(audio).max() <= 1.0

    def rms(a: float, b: float) -> float:
        seg = audio[int(a * soundbed.SR):int(b * soundbed.SR)]
        return float(np.sqrt((seg ** 2).mean()))

    assert rms(12.0, 12.6) > rms(4.0, 4.6)  # shot 4: the low accent lands
    assert rms(24.7, 25.0) < rms(22.0, 22.6)  # fades out at the end


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg не установлен")
def test_assemble_cuts_shots_from_one_full_render(tmp_path):
    reel_id = "reel-07-asmr"  # 15 s; any reel can take a full-length render
    folder = tmp_path / "footage" / reel_id
    folder.mkdir(parents=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=360x640:r=24:d=15",
         "-c:v", "libx264", "-preset", "ultrafast", str(folder / "full.mp4")],
        check=True,
    )
    sources = assemble.find_sources(common.load_json(common.find_content(reel_id)), folder, preview=False)
    assert [s.start_in for s in sources] == [0.0, 2.0, 5.0, 9.0, 12.0]
    out = assemble.assemble(reel_id, "uz", footage_root=tmp_path / "footage", out_dir=tmp_path / "out",
                            preset="ultrafast")
    info = assemble.verify(out, common.style(), 15)
    assert info["duration"] == pytest.approx(15, abs=0.15)
