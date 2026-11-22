"""Compatibility guard for faster-whisper 1.2.1 / PyAV decoder APIs.

As of PyAV 19, av.open() no longer accepts metadata_errors, which
faster-whisper 1.2.1 still passes when decoding audio/video files.
"""


def assert_pyav_compatible(version):
    try:
        major = int(str(version).split('.', 1)[0])
    except (ValueError, TypeError) as exc:
        raise RuntimeError('Неизвестная версия PyAV; требуется av==18.1.0') from exc
    if major < 11 or major >= 19:
        raise RuntimeError(
            f'PyAV {version} несовместим с faster-whisper 1.2.1. '
            'Установите совместимую версию: py -3.12 -m pip install "av==18.1.0"'
        )
