"""Bounded diagnostic tails for long-running FFmpeg/Rust child processes.

A PIPE for stderr may block a decoder when the consumer is busy reading
stdout. Temporary files are disk-backed and avoid the producer deadlock.
"""
import os


def tail_error(stream, limit=400):
    """Return the last `limit` stderr bytes without loading the full log in RAM."""
    stream.flush()
    stream.seek(0, os.SEEK_END)
    stream.seek(max(0, stream.tell() - limit))
    return stream.read().decode('utf-8', 'replace').strip()


def iter_child_blocks(child, stop, block_bytes, *, idle_timeout=120.0,
                      poll_interval=0.1, max_pending=2):
    """Read a child's stdout without trapping the control thread in ``read``.

    A daemon reader may wait for FFmpeg to produce its next complete block, but
    the calling thread can still react to Stop or an idle timeout. Queue
    backpressure limits pending decoded media to ``max_pending * block_bytes``.
    On cancellation, timeout, or premature iterator close, the child is killed.
    This works on Windows as well as POSIX (unlike select() on a pipe).
    """
    import queue
    import threading
    import time

    if block_bytes <= 0 or max_pending <= 0 or idle_timeout <= 0 or poll_interval <= 0:
        raise ValueError('Некорректные параметры потокового чтения')
    if child.stdout is None:
        raise ValueError('Для потокового чтения требуется stdout=PIPE')

    chunks = queue.Queue(maxsize=max_pending)
    cancelled = threading.Event()
    finished = threading.Event()
    reader_errors = []

    def read_stdout():
        try:
            while not cancelled.is_set():
                data = child.stdout.read(block_bytes)
                while not cancelled.is_set():
                    try:
                        chunks.put(data, timeout=poll_interval)
                        break
                    except queue.Full:
                        continue
                if not data:
                    break
        except (OSError, ValueError) as exc:
            if not cancelled.is_set():
                reader_errors.append(exc)
        finally:
            finished.set()

    worker = threading.Thread(target=read_stdout, daemon=True,
                              name='CLIPTORA-subprocess-stream')
    worker.start()
    complete = False
    last_output = time.monotonic()
    try:
        while True:
            if stop.is_set():
                raise InterruptedError('Анализ остановлен пользователем')
            if reader_errors:
                raise RuntimeError('Ошибка чтения FFmpeg: ' + str(reader_errors[0]))
            try:
                block = chunks.get(timeout=poll_interval)
            except queue.Empty:
                if finished.is_set() and chunks.empty():
                    complete = True
                    return
                if time.monotonic() - last_output >= idle_timeout:
                    raise TimeoutError('FFmpeg не отдаёт данные слишком долго; процесс остановлен')
                continue
            if not block:
                complete = True
                return
            last_output = time.monotonic()
            yield block
    finally:
        cancelled.set()
        if not complete and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        worker.join(timeout=1)
