# Тестирование CLIPTORA

В репозитории используются **Python 3.12**, стандартный `unittest`, FFmpeg для интеграционных сценариев и Rust для необязательного нативного сканера.

## Локальные проверки

Из корня репозитория:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
```

Если установлен Rust:

```bash
cargo test --locked --manifest-path rust/scanner/Cargo.toml
cargo build --release --locked --manifest-path rust/scanner/Cargo.toml
```

При отсутствии FFmpeg/FFprobe интеграционные тесты кодирования могут быть пропущены. **Пропущенный тест не равен успешному.** Наличие собранного Rust-сканера проверяется в GitHub Actions.

Для проверки блокирующих FFmpeg-потоков и реакции на остановку:

```bash
python -m unittest discover -s tests -p 'test_streaming_watchdog.py' -v
```

Эти тесты имитируют остановившийся процесс, вывод 4 МиБ данных и отмену посреди чтения. Если FFmpeg доступен, дополнительный тест декодирует двухсекундный MP4 со звуком.

## Автоматическая проверка GitHub Actions

Workflow [`CLIPTORA CI`](../.github/workflows/ci.yml) запускается при изменениях в `main`, на Pull Request и вручную. Проверяются Windows и Ubuntu: Python, сборка и тесты Rust, обнаружение бинарника из Python и регрессионный набор тестов.

**Зелёный CI не означает**, что проверены все пользовательские сценарии, установщик `.exe`, поведение браузера на реальной машине или библиотека 250 ГБ.

## Ручная проверка перед релизом

1. На Windows с Python 3.12 и FFmpeg запусти приложение через `START_WINDOWS.bat`.
2. Скопируй короткую игровую запись в тестовую папку. Просканируй, проанализируй и проверь предложенные моменты.
3. При наличии Whisper проверь появление сегментов речи.
4. Сравни три монтажных варианта, примени один и отмени действие. После перезапуска убедись, что ручные правки сохранились.
5. Создай предпросмотр 480p, затем измени границы клипа и убедись, что предыдущий предпросмотр стал устаревшим.
6. Экспортируй MP4/SRT, воспроизведи результат и проверь звук, переходы, субтитры и сохранность исходников.
7. При наличии Rust проверь совпадение перечисленных файлов с Python-резервным режимом.
8. Для тестов длинных библиотек фиксируй **измеренные** время, память, версии FFmpeg и ошибки. Полный стресс-тест на 250 ГБ ещё не выполнен.

## Как сообщать о результатах

Указывай ОС, версии Python/Rust/FFmpeg, команду, количество успешных/ошибочных/пропущенных тестов и шаги воспроизведения. Не прикладывай личные видеозаписи, стенограммы, локальные пути и секреты. Инструкция по Pull Request — в [CONTRIBUTING.md](../CONTRIBUTING.md).

Чеклист до публичной стабильной версии: [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).


### Windows Portable (GitHub Actions)

Workflow [`Windows Portable EXE`](../.github/workflows/windows-portable.yml) собирает Rust Core, упаковывает приложение PyInstaller в `dist/CLIPTORA/`, запускает smoke-тест **реального** `CLIPTORA.exe` и публикует ZIP-артефакт. Установленный Python в CI нужен только для сборки и тестирования, конечному пользователю — нет. Для локальной сборки на Windows: `cargo build --release --locked --manifest-path rust/scanner/Cargo.toml`, затем `python -m pip install pyinstaller==6.16.0`, затем `python -m PyInstaller --clean --distpath dist --workpath build packaging/cliptora.spec`.

### Portable Core / AI (Windows GitHub Actions)

Workflow `windows-portable.yml` собирает два артефакта: `CLIPTORA-Windows-Portable-Core` и `CLIPTORA-Windows-Portable-AI`. AI-редакция ставит зависимости из `packaging/requirements-portable-ai.txt` и запускает упакованный EXE с `--check-whisper` после старта локального сервера. Это проверка импортов/DLL и CPU int8, **не тест распознавания настоящего звука моделью**. Весов модели нет в архиве.

Локальная сборка AI на Windows после сборки Rust Core:

```powershell
py -3.12 -m pip install pyinstaller==6.16.0 -r packaging/requirements-portable-ai.txt
$env:CLIPTORA_WITH_AI = '1'
py -3.12 -m PyInstaller --clean packaging/cliptora.spec
.\dist\CLIPTORA\CLIPTORA.exe --check-whisper
```

Без переменной `CLIPTORA_WITH_AI` собирается Core. Для работы анализа/экспорта в обеих сборках необходим FFmpeg.


## Windows Portable AI: проверка реального распознавания

В `.github/workflows/windows-portable.yml` только для редакции **AI** выполняется реальный тест: Windows Speech API создаёт короткую озвучку, FFmpeg помещает её в MP4, после чего собранный `CLIPTORA.exe` скачивает модель `tiny.en` и запускает CPU int8 inference. Если модель не распознала речь или не возвращает валидные интервалы, сборка завершается с ошибкой.

Тест не использует и не загружает чужие видеозаписи. Модель хранится в кэше среды CI и не включается в распространяемый архив. Для локальной диагностики:

```powershell
.\CLIPTORA.exe --test-whisper "C:\Видео\пример.mp4" --whisper-test-model tiny --whisper-test-language ru
```

Это smoke-тест запуска модели на коротком файле, а не подтверждение стабильности на сотнях гигабайт.
