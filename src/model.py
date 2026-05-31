import asyncio
import json
import os
import sys
import threading
import time

import numpy as np
from faster_qwen3_tts import FasterQwen3TTS

_LANG_MAP = {
    "en": "english", "zh": "chinese", "de": "german",
    "it": "italian", "pt": "portuguese", "es": "spanish",
    "ja": "japanese", "ko": "korean", "fr": "french", "ru": "russian",
}

_VOICES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "voices")


def _resolve_lang(lang):
    return _LANG_MAP.get(lang.lower(), lang) if len(lang) <= 3 else lang


def load_voices_config():
    path = os.path.join(_VOICES_DIR, "config.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        entries = json.load(f)
    for e in entries:
        e["wav"] = os.path.join(_VOICES_DIR, f"{e['name']}.wav")
        e["txt"] = os.path.join(_VOICES_DIR, f"{e['name']}.txt")
    return entries


def get_default_voice(voices):
    for v in voices:
        if v.get("default"):
            return v
    return voices[0] if voices else None


class Session:
    def __init__(self, engine, ref_audio, ref_text, lang="en", speed=1.0, stream_interval=0.5):
        self.engine = engine
        self.ref_audio = ref_audio
        self.ref_text = ref_text
        self.lang = _resolve_lang(lang)
        self.speed = speed
        self.stream_interval = stream_interval
        self.sample_rate = 24000

    def configure(self, voice=None, lang=None, speed=None):
        if voice is not None:
            wav = os.path.join(_VOICES_DIR, f"{voice}.wav")
            txt = os.path.join(_VOICES_DIR, f"{voice}.txt")
            if not os.path.exists(wav):
                raise ValueError(f"voice '{voice}': {wav} not found")
            self.ref_audio = wav
            self.ref_text = ""
            if os.path.exists(txt):
                with open(txt) as f:
                    self.ref_text = f.read().strip()
        if lang is not None:
            self.lang = _resolve_lang(lang)
        if speed is not None:
            self.speed = speed

    def generate(self, text, lang_code=None):
        chunk_size = max(1, int(12 * self.stream_interval))
        lang = _resolve_lang(lang_code) if lang_code else self.lang
        for audio_chunk, sr, timing in self.engine.generate_voice_clone_streaming(
            text=text,
            language=lang,
            ref_audio=self.ref_audio,
            ref_text=self.ref_text,
            chunk_size=chunk_size,
        ):
            yield {"audio": audio_chunk, "sample_rate": sr}

    async def generate_async(self, text, lang_code=None):
        chunk_size = max(1, int(12 * self.stream_interval))
        lang = _resolve_lang(lang_code) if lang_code else self.lang
        queue = asyncio.Queue()

        def produce():
            for audio_chunk, sr, timing in self.engine.generate_voice_clone_streaming(
                text=text, language=lang, ref_audio=self.ref_audio,
                ref_text=self.ref_text, chunk_size=chunk_size,
            ):
                asyncio.run_coroutine_threadsafe(
                    queue.put({"audio": audio_chunk, "sample_rate": sr}),
                    loop,
                )
            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        loop = asyncio.get_event_loop()
        thread = threading.Thread(target=produce, daemon=True)
        thread.start()

        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk


def load_engine(model_path, verbose=False):
    print(f"Loading model from {model_path}...", flush=True)
    t0 = time.time()
    engine = FasterQwen3TTS.from_pretrained(model_path)
    print(f"Loaded in {time.time() - t0:.1f}s", flush=True)
    return engine


def create_session(engine, voice, default_lang="en", speed=1.0, stream_interval=0.5):
    wav = voice["wav"]
    txt = voice["txt"]
    ref_text = ""
    if os.path.exists(txt):
        with open(txt) as f:
            ref_text = f.read().strip()
    return Session(engine, wav, ref_text, lang=default_lang, speed=speed, stream_interval=stream_interval)


def warmup(session):
    print("Warming up model (CUDA graph capture)...", flush=True)
    t0 = time.time()
    for chunk in session.generate("This is a warmup."):
        import numpy as np
        np.array(chunk["audio"])
    print(f"Warmup done in {time.time() - t0:.1f}s", flush=True)
