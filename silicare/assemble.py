"""Assemble a Reels video from shot footage with FFmpeg.

    python -m silicare.assemble reel-01-how-to-apply                 # RU and UZ
    python -m silicare.assemble reel-01-how-to-apply --lang ru
    python -m silicare.assemble reel-01-how-to-apply --preview       # stand-in cards for missing shots
    python -m silicare.assemble reel-01-how-to-apply --font silicare/assets/fonts/Onest-SemiBold.ttf

Footage: silicare/assets/footage/<id>/shot-01.mp4, shot-02.mov, … (video or a
still image). A shot's "footage" field overrides the name, its "in" field sets
the start second inside the clip. An animated reel can instead provide one
full-length render, full.mp4: each shot is then cut from it at its own time. Each shot is cut to its scenario duration,
cropped to fill 1080×1920 and conformed to 24 fps.

Sound: the clips' own sound (object sounds) plus an optional ambient track
(--ambient, looped, quiet), a fade-out at the end and loudness normalisation.
Titles: the ASS file from silicare.build, burned in with the brand font, above
the bottom safe zone. Logo: assets/brand/logo.png over the last shot, if present.

Output: silicare/build/<id>/<id>.<lang>.mp4 (or .preview.mp4 with --preview).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from silicare import build, common
from silicare.check import font_missing_chars

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


class AssembleError(RuntimeError):
    pass


@dataclass
class Source:
    shot: dict
    path: Path | None  # None = stand-in card (preview)
    kind: str  # "video" | "image" | "card"
    has_audio: bool
    start_in: float = 0.0  # second inside the source where the shot begins


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise AssembleError(f"ffmpeg завершился с ошибкой:\n{tail}")
    return proc


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def _has_audio(path: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in probe(path).get("streams", []))


def find_sources(reel: dict, footage_dir: Path, preview: bool) -> list[Source]:
    """Per-shot files win; otherwise one full-length render (full.mp4) feeds every shot."""
    sources, missing = [], []
    full = next((p for p in sorted(footage_dir.glob("full.*")) if p.suffix.lower() in VIDEO_EXT), None)
    full_audio = _has_audio(full) if full else False
    for shot in reel["shots"]:
        candidates = []
        if shot.get("footage"):
            candidates.append(footage_dir / shot["footage"])
        for stem in (f"shot-{shot['n']:02d}", f"{shot['n']:02d}", f"shot-{shot['n']}"):
            candidates += sorted(footage_dir.glob(f"{stem}.*"))
        path = next((p for p in candidates if p.exists() and p.suffix.lower() in VIDEO_EXT | IMAGE_EXT), None)
        if path is None and full is not None:
            sources.append(Source(shot, full, "video", full_audio, float(shot.get("in", shot["start"]))))
        elif path is None:
            missing.append(shot["n"])
            sources.append(Source(shot, None, "card", False))
        elif path.suffix.lower() in IMAGE_EXT:
            sources.append(Source(shot, path, "image", False))
        else:
            sources.append(Source(shot, path, "video", _has_audio(path), float(shot.get("in", 0))))
    if missing and not preview:
        raise AssembleError(
            f"нет исходников для кадров {missing} в {footage_dir}. "
            "Положите shot-NN.mp4 (или .mov, .jpg) или запустите с --preview для черновой сборки."
        )
    return sources


def _filter_path(path: Path) -> str:
    """Escape a path for use inside an ffmpeg filter argument."""
    s = str(path).replace("\\", "/")
    for ch in ("\\", ":", "'", ",", "[", "]", ";"):
        s = s.replace(ch, "\\" + ch)
    return s


def check_safe_zone(style: dict) -> None:
    t, z, v = style["titles"], style["safe_zone"], style["video"]
    if t["bottom_margin_px"] < z["bottom_px"]:
        raise AssembleError(f"титры ниже безопасной зоны: отступ {t['bottom_margin_px']} < {z['bottom_px']} px")
    three_lines = 3 * t["font_size"] * 1.25
    if v["height"] - t["bottom_margin_px"] - three_lines < z["top_px"]:
        raise AssembleError("три строки титров заходят в верхнюю безопасную зону")


def assemble(
    reel_id: str,
    lang: str,
    *,
    font: Path | None = None,
    ambient: Path | None = None,
    preview: bool = False,
    preset: str = "medium",
    out_dir: Path | None = None,
    footage_root: Path | None = None,
    uz_script: str = "cyrl",
    apostrophe: str = "ʻ",
) -> Path:
    if not shutil.which("ffmpeg"):
        raise AssembleError("ffmpeg не найден в PATH")
    style = common.style()
    v, t, a = style["video"], style["titles"], style["audio"]
    check_safe_zone(style)

    reel = build.localize(common.load_json(common.find_content(reel_id)), uz_script, apostrophe)
    if reel["format"] != "reels":
        raise AssembleError(f"{reel_id} — не Reels")

    font_file = (font or common.ROOT / t["font_file"]).resolve()
    titles_text = " ".join(s[f"text_{lang}"] for s in reel["shots"])
    missing = font_missing_chars(font_file, titles_text)
    if missing is None:
        print("Внимание: fontTools не установлен, покрытие шрифта не проверено (pip install fonttools).", file=sys.stderr)
    elif missing:
        raise AssembleError(
            f"шрифт {font_file.name} не содержит {' '.join(sorted(missing))} для титров {lang.upper()}. "
            "Укажите --font с поддержкой узбекского (например assets/fonts/Onest-SemiBold.ttf) "
            "или --uz-script latn."
        )
    font_name = build.font_family_name(font_file, t["font_family"])

    out_dir = out_dir or common.BUILD_DIR / reel["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    cues = build.reel_cues(reel, lang, t["min_card_sec"])
    ass_path = out_dir / f"{reel['id']}.{'uz-latn' if (lang == 'uz' and uz_script == 'latn') else lang}.ass"
    ass_path.write_text(build.to_ass(cues, style, font_name), encoding="utf-8")

    footage_dir = (footage_root or common.ROOT / "assets" / "footage") / reel["id"]
    sources = find_sources(reel, footage_dir, preview)
    if reel.get("production") == "animation" and not any(src.path and src.path.stem == "full" for src in sources):
        print(f"Внимание: для анимации {reel_id} нет рендера {footage_dir.name}/full.mp4; собираю из покадровых файлов.",
              file=sys.stderr)

    W, H, FPS = v["width"], v["height"], v["fps"]
    length = float(reel["length_sec"])
    tmp = Path(tempfile.mkdtemp(prefix="silicare-"))
    inputs: list[str] = []
    chains: list[str] = []
    concat_in: list[str] = []
    idx = 0
    try:
        for src in sources:
            shot = src.shot
            dur = float(shot["end"]) - float(shot["start"])
            start_in = src.start_in
            cover = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
            if src.kind == "video":
                inputs += ["-ss", f"{start_in:.3f}", "-t", f"{dur:.3f}", "-i", str(src.path)]
                chains.append(f"[{idx}:v]setpts=PTS-STARTPTS,{cover},fps={FPS},format=yuv420p,trim=duration={dur:.3f}[v{shot['n']}]")
            elif src.kind == "image":
                inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{dur:.3f}", "-i", str(src.path)]
                frames = round(dur * FPS)
                chains.append(
                    f"[{idx}:v]{cover},zoompan=z='min(zoom+0.0006,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                    f":d=1:s={W}x{H}:fps={FPS},trim=end_frame={frames},setpts=PTS-STARTPTS,format=yuv420p[v{shot['n']}]"
                )
            else:
                label = tmp / f"card-{shot['n']:02d}.txt"
                label.write_text(f"ПРЕВЬЮ · кадр {shot['n']}\n\n{_wrap(shot['visual'], 30)}", encoding="utf-8")
                bg = style["palette"]["linen"].lstrip("#")
                ink = style["palette"]["graphite"].lstrip("#")
                inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"color=c=0x{bg}:s={W}x{H}:r={FPS}"]
                chains.append(
                    f"[{idx}:v]drawtext=fontfile='{_filter_path(common.ROOT / t['font_file'])}'"
                    f":textfile='{_filter_path(label)}':fontcolor=0x{ink}:fontsize=44:line_spacing=14"
                    f":x=(w-text_w)/2:y=h*0.36,format=yuv420p[v{shot['n']}]"
                )
            idx += 1
            if src.has_audio:
                chains.append(
                    f"[{idx - 1}:a]asetpts=PTS-STARTPTS,aresample={a['sample_rate']},"
                    f"aformat=channel_layouts=stereo,apad,atrim=duration={dur:.3f}[a{shot['n']}]"
                )
            else:
                inputs += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", f"anullsrc=r={a['sample_rate']}:cl=stereo"]
                chains.append(f"[{idx}:a]asetpts=PTS-STARTPTS[a{shot['n']}]")
                idx += 1
            concat_in.append(f"[v{shot['n']}][a{shot['n']}]")

        n = len(sources)
        chains.append(f"{''.join(concat_in)}concat=n={n}:v=1:a=1[vc][ac]")
        chains.append(f"[vc]subtitles=filename='{_filter_path(ass_path)}':fontsdir='{_filter_path(font_file.parent)}'[vs]")

        video_out = "vs"
        logo = common.ROOT / style["logo"]["file"]
        if logo.exists():
            last_start = float(reel["shots"][-1]["start"])
            inputs += ["-loop", "1", "-framerate", str(FPS), "-t", f"{length:.3f}", "-i", str(logo)]
            chains.append(
                f"[{idx}:v]scale={style['logo']['width_px']}:-1,format=rgba,"
                f"fade=t=in:st={last_start + 0.3:.3f}:d=0.6:alpha=1[lg]"
            )
            y_ratio = reel.get("logo_y_ratio", style["logo"].get("y_ratio", 0.40))
            chains.append(f"[vs][lg]overlay=x=(W-w)/2:y=H*{y_ratio:.3f}:enable='gte(t,{last_start:.3f})'[vl]")
            video_out = "vl"
            idx += 1

        audio_out = "ac"
        if ambient:
            inputs += ["-stream_loop", "-1", "-i", str(ambient)]
            chains.append(
                f"[{idx}:a]aresample={a['sample_rate']},aformat=channel_layouts=stereo,"
                f"atrim=duration={length:.3f},volume={a['ambient_gain_db']}dB[amb]"
            )
            chains.append("[ac][amb]amix=inputs=2:duration=first:normalize=0[am]")
            audio_out = "am"
            idx += 1
        fade_st = max(0.0, length - a["fade_out_sec"])
        chains.append(
            f"[{audio_out}]afade=t=out:st={fade_st:.3f}:d={a['fade_out_sec']},"
            f"loudnorm=I={a['target_lufs']}:TP=-1.5:LRA=11,aresample={a['sample_rate']}[aout]"
        )

        suffix = ".preview.mp4" if preview else ".mp4"
        tag = "uz-latn" if (lang == "uz" and uz_script == "latn") else lang
        out = out_dir / f"{reel['id']}.{tag}{suffix}"
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
            "-filter_complex", ";".join(chains),
            "-map", f"[{video_out}]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", preset, "-crf", "18", "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-c:a", "aac", "-b:a", "192k", "-ar", str(a["sample_rate"]),
            "-t", f"{length:.3f}", "-movflags", "+faststart", str(out),
        ]
        _run(cmd)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    verify(out, style, length)
    return out


def _wrap(text: str, width: int) -> str:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return "\n".join(lines)


def verify(path: Path, style: dict, length: float) -> dict:
    """Check the render matches the delivery spec; raise if it does not."""
    info = probe(path)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = [s for s in info["streams"] if s["codec_type"] == "audio"]
    num, den = (int(x) for x in video["avg_frame_rate"].split("/"))
    fps = num / den if den else 0
    duration = float(info["format"]["duration"])
    v = style["video"]
    problems = []
    if (video["width"], video["height"]) != (v["width"], v["height"]):
        problems.append(f"размер {video['width']}×{video['height']}")
    if abs(fps - v["fps"]) > 0.01:
        problems.append(f"{fps:.2f} к/с")
    if abs(duration - length) > 0.15:
        problems.append(f"длина {duration:.2f} с вместо {length}")
    if not audio:
        problems.append("нет звука")
    if problems:
        raise AssembleError(f"{path.name}: " + ", ".join(problems))
    return {"width": video["width"], "height": video["height"], "fps": fps, "duration": duration}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сборка Reels Silicare из отснятого")
    parser.add_argument("reel_id")
    parser.add_argument("--lang", choices=["ru", "uz", "both"], default="both")
    parser.add_argument("--font", type=Path, help="шрифт титров вместо style.json")
    parser.add_argument("--ambient", type=Path, help="лицензированный ambient-трек")
    parser.add_argument("--preview", action="store_true", help="карточки вместо недостающих кадров")
    parser.add_argument("--preset", default="medium", help="x264 preset: ultrafast…veryslow")
    parser.add_argument("--uz-script", choices=["cyrl", "latn"], default="cyrl")
    parser.add_argument("--apostrophe", default="ʻ", help="для латиницы: ʻ (U+02BB) или ‘ (U+2018), если шрифт без ʻ")
    parser.add_argument("--footage", type=Path, help="папка с подпапками <id>/ вместо assets/footage")
    args = parser.parse_args(argv)

    langs = ["ru", "uz"] if args.lang == "both" else [args.lang]
    code = 0
    for lang in langs:
        try:
            out = assemble(args.reel_id, lang, font=args.font, ambient=args.ambient,
                           preview=args.preview, preset=args.preset, uz_script=args.uz_script,
                           apostrophe=args.apostrophe, footage_root=args.footage)
            print(f"{lang.upper()}: {out}")
        except AssembleError as exc:
            print(f"{lang.upper()}: ОШИБКА — {exc}", file=sys.stderr)
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
