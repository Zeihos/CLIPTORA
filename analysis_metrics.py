"""Small, dependency-free per-recording wall-clock diagnostics.

Measurements are time spent by the CLIPTORA worker (including child process waits),
not CPU utilization or a full memory profiler. Raw transcript/media data is never
included. Results are bounded per-video and persisted with the existing job queue.
"""
from contextlib import contextmanager
import math
import os
import sys
import time

STAGES = frozenset({'audio', 'transcription', 'motion', 'dialogue'})


def _seconds(value):
    try:
        v = float(value)
        return round(max(0.0, v), 3) if math.isfinite(v) else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


class AnalysisProfile:
    """Time work stages, even if a stage raises or an analysis is cancelled."""

    def __init__(self, media_seconds, clock=None):
        self.clock = clock or time.perf_counter
        self.started = self.clock()
        self.media_seconds = _seconds(media_seconds)
        self.stages = {}

    @contextmanager
    def stage(self, name):
        if name not in STAGES:
            raise ValueError('Unknown analysis stage')
        start = self.clock()
        try:
            yield
        finally:
            self.stages[name] = _seconds(self.stages.get(name, 0) + max(0, self.clock() - start))

    def snapshot(self, *, audio_windows=0, motion_windows=0, transcript_segments=0):
        elapsed = _seconds(self.clock() - self.started)
        return {
            'total_seconds': elapsed,
            'source_seconds': self.media_seconds,
            'speed_x': round(self.media_seconds / elapsed, 2) if elapsed > 0 else 0.0,
            'stages_seconds': dict(sorted(self.stages.items())),
            'audio_windows': max(0, int(audio_windows)),
            'motion_windows': max(0, int(motion_windows)),
            'transcript_segments': max(0, int(transcript_segments)),
        }


def summarize_performance(jobs, files, signature):
    """Aggregate current-signature measurements without retaining historic logs."""
    names = {f['id']: f.get('name', f['id']) for f in files}
    complete = []
    failed_count = 0
    for media_id, job in jobs.items():
        if job.get('signature') != signature or media_id not in names:
            continue
        state = job.get('state')
        if state == 'failed':
            failed_count += 1
        if state != 'complete' or not isinstance(job.get('metrics'), dict):
            continue
        metrics = job['metrics']
        duration = _seconds(metrics.get('total_seconds'))
        complete.append({'id': media_id, 'name': names[media_id], 'seconds': duration,
                         'source_seconds': _seconds(metrics.get('source_seconds')),
                         'speed_x': _seconds(metrics.get('speed_x'))})
    complete.sort(key=lambda entry: (-entry['seconds'], entry['name']))
    total = round(sum(item['seconds'] for item in complete), 3)
    return {'completed': len(complete), 'failed': failed_count,
            'total_completed_seconds': total,
            'average_seconds': round(total / len(complete), 3) if complete else 0.0,
            'slowest': complete[:3]}


def current_python_rss_mib():
    """Approximate current process working set; excludes FFmpeg child memory."""
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                            ('PeakWorkingSetSize', ctypes.c_size_t),
                            ('WorkingSetSize', ctypes.c_size_t),
                            ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                            ('QuotaPagedPoolUsage', ctypes.c_size_t),
                            ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                            ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                            ('PagefileUsage', ctypes.c_size_t),
                            ('PeakPagefileUsage', ctypes.c_size_t)]
            info = PROCESS_MEMORY_COUNTERS()
            info.cb = ctypes.sizeof(info)
            get_process = ctypes.windll.kernel32.GetCurrentProcess
            get_process.restype = wintypes.HANDLE
            get_usage = ctypes.windll.psapi.GetProcessMemoryInfo
            get_usage.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD)
            if not get_usage(get_process(), ctypes.byref(info), info.cb):
                return None
            count = int(info.WorkingSetSize)
        elif sys.platform.startswith('linux'):
            with open('/proc/self/statm', encoding='ascii') as handle:
                rss_pages = int(handle.read().split()[1])
            count = rss_pages * os.sysconf('SC_PAGE_SIZE')
        else:
            return None
        return round(count / (1024 * 1024), 1)
    except (OSError, AttributeError, ValueError, IndexError):
        return None
