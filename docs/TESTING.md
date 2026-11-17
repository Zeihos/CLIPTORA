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
