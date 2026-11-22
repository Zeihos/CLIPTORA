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
