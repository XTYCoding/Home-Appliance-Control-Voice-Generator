"""
使用 Microsoft Edge 在线神经语音合成（edge-tts），MP3 缓存在 audio_cache/。
缓存键：SHA256(音色 + 换行 + 文案)，文案或音色变化即视为新文件。
"""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import edge_tts

# 中文女声；可改为 zh-CN-YunxiNeural、zh-CN-YunyangNeural 等
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"

CACHE_DIR = Path(__file__).resolve().parent / "audio_cache"


def _cache_key(phrase: str, voice: str) -> str:
    payload = f"{voice}\n{phrase.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_mp3_path(phrase: str, voice: str = DEFAULT_VOICE) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{_cache_key(phrase, voice)}.mp3"


async def _synthesize_to_file(text: str, voice: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def ensure_mp3_cached(phrase: str, voice: str = DEFAULT_VOICE) -> Path:
    """
    若缓存文件不存在则请求 Edge TTS 并写入 audio_cache。
    已存在则直接返回路径。
    """
    phrase = phrase.strip()
    if not phrase:
        raise ValueError("语音文案为空")
    path = cached_mp3_path(phrase, voice)
    if path.is_file():
        return path
    asyncio.run(_synthesize_to_file(phrase, voice, str(path)))
    return path


def ensure_and_get_path(phrase: str, voice: str = DEFAULT_VOICE) -> tuple[Path, bool]:
    """
    返回 (缓存文件路径, 是否命中缓存)。
    若无缓存则先合成并写入缓存。
    """
    phrase = phrase.strip()
    if not phrase:
        raise ValueError("语音文案为空")
    path = cached_mp3_path(phrase, voice)
    cache_hit = path.is_file()
    if not cache_hit:
        asyncio.run(_synthesize_to_file(phrase, voice, str(path)))
    return path, cache_hit


def warm_cache(appliances: list[dict], voice: str = DEFAULT_VOICE) -> tuple[int, int]:
    """
    为配置中所有非空语音文案确保存在 MP3。
    返回 (本次新生成的数量, 已存在跳过的数量)。
    """
    generated = 0
    skipped = 0
    for app in appliances:
        for cmd in app.get("commands") or []:
            phrase = (cmd.get("phrase") or "").strip()
            if not phrase:
                continue
            path = cached_mp3_path(phrase, voice)
            if path.is_file():
                skipped += 1
                continue
            asyncio.run(_synthesize_to_file(phrase, voice, str(path)))
            generated += 1
    return generated, skipped


def prune_stale_cache(appliances: list[dict], voice: str = DEFAULT_VOICE) -> int:
    """
    删除 audio_cache 中未被当前配置引用的 .mp3（文案或音色变更后遗留的文件）。
    返回删除文件个数。
    """
    valid_names: set[str] = set()
    for app in appliances:
        for cmd in app.get("commands") or []:
            phrase = (cmd.get("phrase") or "").strip()
            if phrase:
                valid_names.add(f"{_cache_key(phrase, voice)}.mp3")
    if not CACHE_DIR.is_dir():
        return 0
    removed = 0
    for f in CACHE_DIR.glob("*.mp3"):
        if f.name not in valid_names:
            try:
                f.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def synthesize_and_play(phrase: str, voice: str = DEFAULT_VOICE) -> None:
    """已弃用：仅保留兼容。"""
    ensure_and_get_path(phrase, voice)
