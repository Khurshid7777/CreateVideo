"""Uzbek Cyrillic -> Uzbek Latin (official alphabet, 1995 with later spelling of oʻ gʻ).

Needed if the lawyer requires Latin script for Uzbek advertising text (task 1):
the subtitles and captions stay in Cyrillic in the JSON and are converted on
export. ``apostrophe`` lets you pick ʻ (U+02BB, official) or ‘ (U+2018) for
fonts that lack U+02BB — Manrope is one of them.

    python -m silicare.translit "Чандиқ 12–18 ой пишади"
"""

from __future__ import annotations

import sys

VOWELS = set("аеёиоуэюяўАЕЁИОУЭЮЯЎ")

BASE = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ч": "ch", "ш": "sh", "э": "e",
    "ю": "yu", "я": "ya", "ё": "yo", "қ": "q", "ҳ": "h", "ь": "",
}


def to_latin(text: str, apostrophe: str = "ʻ") -> str:
    out: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        low = ch.lower()
        prev = text[i - 1] if i > 0 else ""
        nxt = text[i + 1] if i + 1 < n else ""
        word_start = not prev.isalpha()
        if low == "е":
            lat = "ye" if word_start or prev in VOWELS or prev in "ъЪ" else "e"
        elif low == "ц":
            lat = "ts" if (prev in VOWELS and not word_start) else "s"
        elif low == "ў":
            lat = "o" + apostrophe
        elif low == "ғ":
            lat = "g" + apostrophe
        elif low == "ъ":
            lat = "ʼ" if apostrophe == "ʻ" else "’"
        elif low in BASE:
            lat = BASE[low]
        else:
            out.append(ch)
            continue
        if ch.isupper() and lat:
            # Whole-word capitals keep digraphs upper (ШАРТ -> SHART), else Sh.
            if nxt.isupper() or (prev.isupper() and not nxt.isalpha()):
                lat = lat.upper()
            else:
                lat = lat[0].upper() + lat[1:]
        out.append(lat)
    return "".join(out)


if __name__ == "__main__":
    print(to_latin(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else sys.stdin.read()))
