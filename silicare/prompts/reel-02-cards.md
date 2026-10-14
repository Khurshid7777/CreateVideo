# Reels 2 «Миф или факт»: карточки

По сценарию ТЗ ролик снимается: карточки из плотной бумаги на льне, переворот в замедлении вдвое. В таблице задач для Claude Code «сцены мифов» отнесены к анимации, а в стратегии — «text cards from Claude Design plus a переворота sound, no filming». Выберите один путь.

| Путь | Что нужно | Как собрать |
| --- | --- | --- |
| Съёмка (сценарий ТЗ) | 4 карточки из плотной бумаги, лён, мягкий свет сверху, штатив | Клипы `shot-01.mp4` … `shot-06.mp4` в `assets/footage/reel-02-myth-or-fact/`, затем `python -m silicare.assemble reel-02-myth-or-fact` |
| Карточки из Claude Design | 6 изображений 1080×1920 по бренд-киту | PNG `shot-01.png` … `shot-06.png` в ту же папку: сборка даст медленный наезд вместо переворота |
| Видеосервис | Промпт ниже, по клипу на кадр | Как для съёмки |

Текст на карточках в кадре не печатается и не генерируется: титры RU и UZ накладывает сборка, так один исходник служит обеим версиям.

Промпт для видеосервиса, кадры 2–5 (меняется только цвет фона карточки):

```text
Top-down view of a blank thick cream paper card lying on beige linen #F3E9E1, a hand-free card flip in half-speed slow motion revealing the blank back side, soft diffused daylight from above, subtle paper texture, locked overhead camera, no zoom, no cuts. No text, no letters, no logos, no faces, no red. 9:16 vertical, 24 fps.
```

Для кадра 4 добавьте `a small deep teal #1F6F6B accent stripe on the card`, для кадра 5 — `powder pink #E8C9C0 background instead of linen`.
