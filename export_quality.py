"""Opt-in, deterministic FFmpeg filters for a streaming clip-by-clip export.

Crossfades that overlap clips would change timeline/subtitle offsets, so this
module deliberately implements short non-overlapping fades *through black*.
Default settings preserve existing CLIPTORA hard-cut output.
"""
import math


def validate_export_quality(normalize_audio=False, fade_ms=0):
    """Validate the public API boundary without implicit bool/int conversions."""
    if type(normalize_audio) is not bool:
        raise ValueError('Нормализация звука: ожидается true или false')
    if type(fade_ms) is not int or fade_ms not in (0, 150, 300):
        raise ValueError('Переходы: выберите 0, 150 или 300 мс')
    return normalize_audio, fade_ms


def make_export_filters(duration, width, height, *, zoom=False, normalize_audio=False, fade_ms=0):
    """Return (video_filter, audio_filter) for one clip, with no timeline overlap.

    Fades for very short clips shrink to at most one quarter of the clip;
    audio fades are after loudness processing to prevent boosted click tails.
    """
    validate_export_quality(normalize_audio, fade_ms)
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError('Длительность фрагмента должна быть положительной')
    if zoom:
        scale_w=int(width*1.08)//2*2
        scale_h=int(height*1.08)//2*2
    else:
        scale_w,scale_h=width,height
    video=f'scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,fps=30'
    audio='loudnorm=I=-16:TP=-1.5:LRA=11' if normalize_audio else ''
    if fade_ms:
        fade=round(min(fade_ms/1000.0, duration/4), 3)
        start=round(duration-fade,3)
        # Keep all filter timestamps non-negative and within the trimmed clip.
        video+=f',fade=t=in:st=0:d={fade},fade=t=out:st={start}:d={fade}'
        audio+=(',' if audio else '')+f'afade=t=in:st=0:d={fade},afade=t=out:st={start}:d={fade}'
    audio+=(',' if audio else '')+'aresample=48000'
    return video,audio
