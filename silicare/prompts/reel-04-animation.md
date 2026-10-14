# Reels 4 «Почему рубец становится грубым»: анимация

Ролик без съёмки: срез кожи, коллаген, влага, слой силикона. 25 секунд, 6 кадров, палитра беж #F3E9E1, графит #2B2B2B, тил #1F6F6B, без красного. Титры и логотип накладывает `python -m silicare.assemble` из `reels/reel-04-why-scar-gets-rough.json`, поэтому в самих клипах текста нет.

## Решение

Владелец выбрал путь A: код анимации на Remotion. Исходники — `silicare/remotion/reel-04/`, порядок сборки — в `silicare/README.md`, раздел «Анимация ролика 4». Промпты ниже остаются запасным вариантом, если понадобится более «живой» вид от видеосервиса.

## Путь B: промпты по кадрам

Общие правила для всех кадров (по навыку `.agents/skills/seedance-2-0`): один клип на кадр, явно сказано, что камера делает и чего не делает, никакого текста и логотипов в кадре. Звук сервиса не используем: звук собирается при монтаже.

Хвост, который добавляется к каждому промпту:

```text
Premium medical minimalism, soft diffused side light, warm beige #F3E9E1 and graphite #2B2B2B palette with a calm deep teal #1F6F6B accent, clean scientific illustration look, shallow depth of field, 9:16 vertical, 24 fps. No text, no letters, no logos, no red, no blood, no open wound, no gore, no faces, no hands, no cuts.
```

| Кадр | Время | Промпт |
| --- | --- | --- |
| 1 | 0–3 с | `Extreme macro of smooth human skin surface, fine natural texture and pores, camera glides slowly along the surface from left to right, steady, no zoom, no rotation.` |
| 2 | 3–7 с | `Camera slowly dives through the skin surface into a clean cross-section: thin translucent epidermis layer above a softer dermis layer, delicate thin collagen fibers forming in the dermis, slow forward push, no shake.` |
| 3 | 7–12 с | `Static cross-section of skin; tiny clear moisture droplets rise and drift up and away from the surface, the colour temperature warms slightly, collagen fibers beneath start to multiply, locked camera, no zoom.` |
| 4 | 12–16 с | `Static cross-section; collagen fibers thicken and crowd together, the skin surface above them slowly bulges into a firm raised ridge, calm graphite and beige tones, locked camera, no zoom.` |
| 5 | 16–21 с | `A thin transparent silicone sheet gently settles onto the raised skin surface from above; moisture droplets drift back down beneath the sheet; colour shifts toward calm deep teal; slow, soft motion, locked camera.` |
| 6 | 21–25 с | `Under the transparent silicone sheet the collagen fibers slowly relax and align into calmer, more even lines; the surface flattens a little; leave the upper centre of the frame calm and empty for a logo; very slow push-in, no cuts.` |

Кадр 6 показывает «может помочь», а не результат: волокна выравниваются слегка, рубец не исчезает.

## Как собрать

1. Сохраните клипы как `silicare/assets/footage/reel-04-why-scar-gets-rough/shot-01.mp4` … `shot-06.mp4`.
2. Сверьте каждый кадр с формулировками механизма (claims в JSON) и с научными ссылками (задача 9).
3. `python -m silicare.assemble reel-04-why-scar-gets-rough --ambient <лицензированный drone-трек>`
