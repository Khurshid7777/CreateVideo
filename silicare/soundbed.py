"""Procedural sound bed for the animated Reels 4, following the brief's sound column.

    python -m silicare.soundbed            # -> silicare/build/reel-04-why-scar-gets-rough/soundbed.wav
    python -m silicare.assemble reel-04-why-scar-gets-rough \
        --ambient silicare/build/reel-04-why-scar-gets-rough/soundbed.wav

Shot by shot (brief): low drone → rising tone → tone holds → low accent → tone
brightens → soft chord. Built from sines and filtered noise, so there is no
licence to clear; swap in a licensed track whenever you prefer.
"""

from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

import numpy as np

from silicare import common

SR = 48_000
REEL_ID = "reel-04-why-scar-gets-rough"


def _ramp(t: np.ndarray, a: float, b: float) -> np.ndarray:
    """0 before a, 1 after b, smooth (raised cosine) in between."""
    x = np.clip((t - a) / (b - a), 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * x)


def _tone(t: np.ndarray, freq, detune: float = 0.0) -> np.ndarray:
    """Sine with a time-varying frequency (phase integrated, so glides stay clean)."""
    f = np.broadcast_to(np.asarray(freq, dtype=float), t.shape) + detune
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def _soft_noise(n: int, seed: int, smooth: float = 0.995) -> np.ndarray:
    rng = np.random.default_rng(seed)
    white = rng.standard_normal(n)
    out = np.empty(n)
    acc = 0.0
    for i, w in enumerate(white):  # one-pole low-pass: a warm, airy bed
        acc = smooth * acc + (1 - smooth) * w
        out[i] = acc
    return out / (np.abs(out).max() + 1e-9)


def reel04(duration: float = 25.0) -> np.ndarray:
    """Stereo float array (n, 2) in [-1, 1]."""
    t = np.arange(int(duration * SR)) / SR
    channels = []
    for side, detune in ((0, -0.25), (1, 0.25)):
        # Shot 1 onward: low drone, slowly breathing.
        breath = 0.85 + 0.15 * np.sin(2 * np.pi * 0.11 * t + side)
        drone = (0.5 * _tone(t, 55, detune) + 0.3 * _tone(t, 82.5, -detune) + 0.15 * _tone(t, 110, detune))
        drone *= 0.32 * breath * _ramp(t, 0, 1.6) * (1 - 0.5 * _ramp(t, 21, 24))

        # Shots 2–3: a tone rises (A3 → D4) and holds.
        glide = 220 + (293.66 - 220) * _ramp(t, 3, 7)
        glide = glide + (329.63 - 293.66) * _ramp(t, 16, 19)  # shot 5: brightens toward E4
        vibrato = 1 + 0.002 * np.sin(2 * np.pi * 4.5 * t)
        rising = _tone(t, glide * vibrato, detune) * 0.11 * _ramp(t, 3, 7) * (1 - _ramp(t, 21, 23))

        # Shot 4: one low accent as the ridge rises.
        hit_t = np.clip(t - 12.0, 0, None)
        accent = np.where(t >= 12.0, np.sin(2 * np.pi * 49 * hit_t) * np.exp(-hit_t / 1.1), 0.0) * 0.42

        # Shot 5: the sheet lands; a soft high shimmer opens up.
        shimmer = (0.5 * _tone(t, 659.25, detune) + 0.35 * _tone(t, 987.77, -detune))
        shimmer *= 0.05 * _ramp(t, 16.5, 18.5) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.7 * t)) * (1 - _ramp(t, 21, 23))

        # Shot 6: a soft A major add9 chord.
        chord = sum(_tone(t, f, detune * 0.5) * a for f, a in ((220.0, 0.5), (277.18, 0.4), (329.63, 0.38), (493.88, 0.25)))
        chord *= 0.12 * _ramp(t, 21, 22.2)

        air = _soft_noise(len(t), seed=4 + side) * 0.05 * _ramp(t, 0, 2)
        channels.append(drone + rising + accent + shimmer + chord + air)

    mix = np.stack(channels, axis=1)
    mix *= (1 - _ramp(t, duration - 1.6, duration))[:, None]
    mix = np.tanh(1.2 * mix)  # gentle saturation keeps the peaks round
    return mix / (np.abs(mix).max() + 1e-9) * 10 ** (-3 / 20)


def write_wav(path: Path, audio: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Звуковая подложка для Reels 4")
    parser.add_argument("--out", type=Path, default=common.BUILD_DIR / REEL_ID / "soundbed.wav")
    args = parser.parse_args(argv)
    length = float(common.load_json(common.find_content(REEL_ID))["length_sec"])
    print(write_wav(args.out, reel04(length)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
