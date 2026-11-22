"""Real packaged Whisper inference on a synthetic video, for Windows CI.

This script runs against a Windows *exe*, not the Python source interpreter.
It does not print private recognized speech or retain the model in git.
"""
import json
import subprocess
import sys
from pathlib import Path


def create_video(wav_file, video_file, ffmpeg_bin):
    wav = Path(wav_file).resolve()
    video = Path(video_file).resolve()
    if not wav.is_file() or wav.stat().st_size < 10000:
        raise RuntimeError('Missing synthesized speech fixture')
    command = [str(ffmpeg_bin), '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'lavfi', '-i', 'color=c=navy:s=320x180:r=12',
               '-i', str(wav), '-c:v', 'mpeg4', '-q:v', '8', '-c:a', 'aac',
               '-b:a', '128k', '-shortest', str(video)]
    subprocess.run(command, check=True, timeout=90)
    if not video.is_file() or video.stat().st_size < 10000:
        raise RuntimeError('FFmpeg did not produce a video with speech')
    return video


def verify_inference(exe_file, video_file):
    exe = Path(exe_file).resolve()
    media = Path(video_file).resolve()
    if not exe.is_file() or not media.is_file():
        raise FileNotFoundError('Executable or speech video is missing')
    run = subprocess.run([str(exe), '--test-whisper', str(media),
                          '--whisper-test-model', 'tiny.en',
                          '--whisper-test-language', 'en'],
                         capture_output=True, text=True, encoding='utf-8',
                         errors='replace', timeout=420)
    if run.returncode:
        raise RuntimeError('Packaged Whisper inference failed: ' + run.stderr[-4000:])
    try:
        result = json.loads(run.stdout.strip())
    except ValueError as exc:
        raise RuntimeError('Whisper diagnostics did not produce valid JSON: ' + run.stdout[-1200:]) from exc
    if result.get('ok') is not True or result.get('segments', 0) < 1 or result.get('recognized_chars', 0) < 8:
        raise AssertionError('Whisper returned no intelligible speech segments: ' + str(result))
    print('Packaged Whisper real video inference OK:', result)
    return result


if __name__ == '__main__':
    if len(sys.argv) != 4:
        raise SystemExit('Usage: smoke_whisper_inference.py EXE INPUT_WAV OUTPUT_MP4')
    import imageio_ffmpeg
    video = create_video(sys.argv[2], sys.argv[3], imageio_ffmpeg.get_ffmpeg_exe())
    verify_inference(sys.argv[1], video)
