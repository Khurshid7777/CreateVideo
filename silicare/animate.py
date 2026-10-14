"""Render an animated reel's Remotion composition to assets/footage/<id>/full.mp4.

    python -m silicare.animate reel-04-why-scar-gets-rough           # final, 1080×1920
    python -m silicare.animate reel-04-why-scar-gets-rough --draft   # half size, faster

Goes through the repository's video_compose tool in atelier mode, which stages
the sources into remotion-composer/ and runs its post-render review. Needs
`cd remotion-composer && npm ci` once. Where Remotion cannot download its own
browser (sandboxes, CI), set REMOTION_BROWSER_EXECUTABLE to a local Chromium
headless shell; remotion-composer/remotion.config.ts picks it up.

Then: python -m silicare.assemble <id> (titles, logo, sound, RU and UZ).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from silicare import common


def render(reel_id: str, draft: bool = False) -> Path:
    reel = common.load_json(common.find_content(reel_id))
    spec = reel.get("remotion")
    if reel.get("production") != "animation" or not spec:
        raise SystemExit(f"{reel_id}: не анимация или нет поля remotion в JSON")
    from tools.video.video_compose import VideoCompose  # repository tool; run from the repo root

    folder = common.ROOT / "remotion" / spec["dir"]
    out = common.ROOT / "assets" / "footage" / reel_id / "full.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    bespoke = {
        "entry": str(folder / "index.tsx"),
        "composition_id": spec["composition_id"],
        "art_direction": str(folder / "art-direction.md"),
        "crf": 16,
    }
    if draft:
        bespoke["scale"] = 0.5
    result = VideoCompose().execute({
        "operation": "render",
        "output_path": str(out),
        "edit_decisions": {"render_runtime": "remotion", "composition_mode": "atelier", "bespoke": bespoke},
    })
    if not result.success:
        raise SystemExit(f"рендер не удался: {result.error}")
    review = (result.data or {}).get("final_review") or {}
    for issue in review.get("issues_found", []):
        # The animation is silent by design (sound is added by assemble.py) and has no narration.
        if "silent" not in issue and "narration_transcript" not in issue:
            print(f"Ревью: {issue}", file=sys.stderr)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Рендер анимации Reels через Remotion")
    parser.add_argument("reel_id")
    parser.add_argument("--draft", action="store_true", help="половинный размер для быстрой проверки")
    args = parser.parse_args(argv)
    print(render(args.reel_id, args.draft))
    return 0


if __name__ == "__main__":
    sys.exit(main())
