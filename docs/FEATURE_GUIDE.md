# CLIPTORA — detailed feature guide

Historical notes and practical warnings for individual alpha features, moved here to keep the [README](../README.md) focused on the current application.

### Адаптивная длительность кульминаций (v0.1.14)

При создании новой подборки CLIPTORA учитывает, что реакция может продолжаться дольше одного резкого звука: теперь предложенные фрагменты иногда расширяются до конца аудиовсплеска, заметного движения или реплики собеседника. Если перед пиком была короткая подводка, она тоже может попасть в предложение. Длина звукового фрагмента ограничена 20 секундами.

- При совпадении звукового пика, речи и движения программа немного повышает **эвристический** приоритет и показывает причину в блоке «Основание». Это не распознавание убийства, победы, шутки, смеха или эмоции.
- Вся функция работает по существующему локальному анализу: заново обрабатывать неизменённые видео не нужно.
- Чтобы увидеть новые предложения, заново сформируйте подборку или воспользуйтесь сравнением трёх вариантов. **Не применяйте новую подборку поверх ручных правок без проверки**: сначала сохраните резервную копию `project.json` или используйте историю отмены.
- Условия разных игр и микрофонов различаются. Сцены нужно вручную проверить на качество и подправить границы при необходимости. Стресс-тест на 250 ГБ ещё не проводился.

### Темп монтажа и тихие паузы (v0.1.13)

В разделе **Экспорт** выберите темп: **Исходный** (по умолчанию, без изменений), **Динамичный** или **Быстрый**. После этого нажмите «Собрать предпросмотр» и сравните с исходной версией. Тот же темп применяется к финальному MP4 и учтён при создании SRT.

- Склейки происходят **только между распознанными репликами** и только в достаточно тихих участках. При наличии результатов анализа движения активные игровые события тоже защищены от сокращения.
- Для работы требуется сохранённая стенограмма `faster-whisper` **и** аудиоанализ; без них сцены не сокращаются. Обнаружение пауз — эвристика, а не полноценный анализ смысла или точная классификация звуков.
- **Динамичный** режим ищет пробелы между репликами от 2 с, **Быстрый** — от 1.1 с. Оба оставляют запас до и после речи; не больше 24 сокращений в одном исходном фрагменте.
- Сокращение применяется **при экспорте**, а не к ручному черновику или исходному видео. Предпросмотр и финальный экспорт используют одну реализацию. Переключение режима делает прежний предпросмотр неактуальным.
- В `*.json` рядом с экспортом записаны режим, количество сокращений и удалённая длительность. Пока нет проверки качества итогового монтажа на сотнях гигабайт.

### Предпросмотр готового монтажа (v0.1.12)

В разделе **Экспорт** после выбора сцен и параметров звука/переходов нажмите **«Собрать предпросмотр · первые 2 мин»**. CLIPTORA создаст отдельный MP4 в 480p в рабочей папке `previews/`, сохранив порядок сцен, обрезку, зум, нормализацию и затухания. Файл можно воспроизвести и перемотать в браузере.

- Режим ограничен **первыми 120 секундами** выбранного черновика. Длинный монтаж целиком формируется обычным экспортом.
- Предпросмотр **не меняет** исходные записи, ручной монтаж, субтитры и `last_output`. Встраивание субтитров не предусмотрено.
- Если изменить границы, набор клипов или настройки звука/переходов, предпросмотр станет устаревшим — создайте новый.
- Для работы необходим FFmpeg; предпросмотр требует кодирования и не является рендерингом в реальном времени.

### Проверяем качество подбора (v0.1.15)

Новый раздел **«Контроль качества подбора»** позволяет сравнить автоматические предложения с **эталонными моментами, которые ты сам просмотрел и отметил**.

1. После сканирования выбери конкретную запись, укажи начало и конец действительно интересной сцены в секундах и нажми **«Отметить момент»**. Разметь *все* важные эпизоды нескольких выбранных записей, а не только те, которые уже нашёл CLIPTORA.
2. Нажми **«Оценить подборку»**. Для включённых в текущий черновик клипов измеряется пересечение с эталонами (IoU), где совпадением считается **IoU ≥ 0,30** и каждому эталону/клипу разрешена только одна пара.
3. Снова нажми **«Сравнить 3 варианта»**: у сбалансированного, диалогового и экшен-вариантов теперь показываются Precision (точность), Recall (полнота) и F1, если есть эталонная разметка. Сравнение не заменяет ручной монтаж.

**Что это значит:** Precision — доля выбранных клипов, совпавших с эталонами; Recall — доля эталонов, найденных в подборке; F1 — гармоническое среднее. В оценке участвуют **только видео, для которых создан хотя бы один эталон**; клипы с неразмеченных записей исключаются и учитываются отдельно. Если эталонов нет, метрики **не вычисляются**, а не равняются нулю.

**Ограничения:** это не автоматическая оценка смешности, качества шуток или настроения зрителя. Неполная разметка делает показатели ненадёжными, а порог IoU условен. Не размечай лишь уже автоматически выбранные клипы — так ты искусственно завысишь оценку. До 500 эталонов хранятся отдельно от черновика в локальном `project.json`; они сохраняются при перезапуске и исчезают, если соответствующий исходный файл удалён или изменён при повторном сканировании. Изменение исходной папки сбрасывает разметку. Рекомендуется сделать резервную копию `project.json` перед массовой переработкой библиотеки. Новая функция работает полностью локально, без скачивания моделей и отправки видео в сеть.

## Compare three edit drafts safely (v0.1.10)

After processing your videos, choose **Compare 3 variants** under Draft editing. CLIPTORA builds balanced, dialogue and action options from cached audio, speech and movement analysis. This preview never replaces `project.json` or your manual edits. Click ▶ on a suggested segment to inspect it locally.

Click **Apply** only after reviewing the option you prefer. The complete previous clip list, including disabled segments, custom labels, zoom and trims, is saved in `plan_history` within `project.json` (last five replacements retained). Click **Undo apply** to restore the previous plan, even after restarting the program. Preview tokens become invalid when the project changes; compare again after a rescan or manual edit. The legacy `/api/plan` endpoint also keeps a recoverable snapshot.

The presets adjust simple ranking scores. They do not recognize comedic intent or guarantee quality. Back up the complete workspace before large changes and avoid storing generated output inside the recordings directory.

## CLIPTORA 0.1.6 queue troubleshooting

- Stopping or closing the application during a video does not keep partial transcription for that video; it is processed from the start on resume. Completed **other** videos remain finished.
- A failed video is marked as failed. Other recordings still process. Press **Analyze / Continue** to retry failed files.
- If a file was modified since scanning, rescan the footage directory before retrying analysis.
- Thread control applies to FFmpeg decoding/filters and Whisper CPU inference; it cannot guarantee a fixed memory or CPU percentage. Queue runs one recording at a time.
- Project metadata and queue are stored locally in `project.json`. Keep a backup of it when editing a large library.

## CLIPTORA 0.1.7 — audio reaction highlights

Use the existing workflow **Scan → Analyze → Create selection**. For already-analyzed unchanged files, click **Create selection** again to rebuild the proposed clips using the new relative-reaction algorithm. This action replaces the draft selection, so **back up or export any manually reviewed draft first**. Simply upgrading does not destroy saved clip edits.

Each automatically suggested clip may include **Основание** (why it was suggested): sound spike compared to nearby sound, nearby speech and/or motion. These are statistical clues, **not** verified jokes, emotions, speakers or game events. The ``score/100`` is a ranking heuristic, not a calibrated probability.

The new detector only uses existing 0.5-second RMS levels and optional speech/motion metadata; it never sends gameplay recordings to an external service. A first scan and speech analysis can still take time. Audio-only videos work without Whisper or Rust.

## CLIPTORA 0.1.8 — speech context windows

The **Create selection** action now proposes bounded dialogue windows (at most 36 seconds) which try to preserve an earlier setup, a plausible punchline/reaction and a short follow-up/beat. Signals come from existing Whisper transcript timestamps, optional local Ollama heuristic ratings and the previously recorded audio-reaction metadata; the app **cannot reliably identify actual jokes or speakers**. Results remain reviewable, editable suggestions, not guaranteed funny clips.

The new context algorithm reuses cached analysis from 0.1.7: **you do not need to rescan or retranscribe** an unchanged recording. **Creating a new selection replaces the entire current draft** (including manually reviewed clips), so keep a backup of `project.json` or export your draft first. Just upgrading preserves the project without rewriting the draft.

## CLIPTORA 0.1.9 — shortlist quality and dialogue comparison

After the existing **Scan → Analyze** steps, press **Create selection** to rebuild a shortlist with the new local ranking stage. This version reuses existing analysis (Whisper / audio / motion) and adds no model downloads. It gives a small preference to extended dialogue with an earlier setup and later reply, and penalizes very short dialogue with little context. It suppresses near-identical, informative transcript passages when duration is comparable; generic labels like "sound reaction" never cause deduplication. Different punchlines are intentionally retained unless their text is extremely similar.

The interface now shows the original raw heuristic score through the ranking badge tooltip, the adjusted selection priority, the reasons for its adjustment and a summary of overlaps / duplicate suggestions skipped during the selection pass. **These signals do not prove that two clips contain the same visual event, or that a joke is funny.** If auto-transcription repeats or changes words, some repeated scenes may still pass or distinct dialogue may be filtered. Please review before exporting.

The `selection_summary` in local `project.json` describes the **last automatic shortlist** only. Subsequent manual clip edits do not recompute this history. Rebuilding the draft replaces previous manual edits as in earlier versions; make a backup or export before pressing Create selection again. Upgrading the application itself does not rebuild the draft or discard cached analysis.

## Export quality controls (v0.1.11)

Under **Export**, optional **Normalize volume** runs FFmpeg's single-pass `loudnorm=I=-16:TP=-1.5:LRA=11` on each selected scene independently, followed by 48 kHz stereo resampling. This is an approximation, not guaranteed integrated loudness across a complete finished movie; very quiet clips may have background noise amplified. Leave it off when you prefer original dynamics. The program never modifies the source recordings.

**Scene joins** can use hard cuts (default) or 150/300 ms **fade through black**. This is *not* an overlapping crossfade. Every segment retains its duration, so subtitle timestamps and montage timing do not change. Very short segments receive proportionally shorter fades to avoid all-black clips. Hard cuts are usually better for fast comedic/action pacing.

The MP4 is first written to a hidden `.partial.mp4` in the render directory, and published as a final `.mp4` only when FFmpeg successfully finishes concatenating the scene files. A failed export cleans its temporary files and does not overwrite `last_output` or previous completed renders. Each render uses a microsecond timestamp to avoid accidental filename collisions. Export options are recorded in the sidecar JSON manifest. These safeguards do not ensure successful subtitle burn-in in all cases; a separate SRT remains available.
