"""Audio playback abstraction layer."""

import queue
import threading

import numpy as np
import sounddevice as sd


def list_output_devices():
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0:
            print(f"  {i}: {d['name']}")


def resolve_device(name_or_index):
    if name_or_index is None:
        return None
    try:
        return int(name_or_index)
    except ValueError:
        for i, d in enumerate(sd.query_devices()):
            if name_or_index.lower() in d["name"].lower() and d["max_output_channels"] > 0:
                return i
        return None


def to_float32(audio):
    """Normalize WAV data to float32 in [-1, 1]."""
    if audio.dtype == np.float32 or audio.dtype == np.float64:
        return audio.astype(np.float32)
    return audio.astype(np.float32) / 32768.0


def play_audio(samples, sample_rate, device=None):
    """Play float32 samples and block until done."""
    sd.play(samples, sample_rate, device=device)
    sd.wait()


class StreamPlayer:
    """Play audio chunks incrementally with gapless output.

    Wraps sd.OutputStream with a thread that pulls chunks from a queue.
    First chunk starts playback immediately; subsequent chunks queue up
    and play with no gap.
    """

    def __init__(self, sample_rate, device=None, channels=1, dtype="float32"):
        self.sample_rate = sample_rate
        self.device = device
        self.channels = channels
        self.dtype = dtype
        self._q = queue.Queue()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        with sd.OutputStream(
            samplerate=self.sample_rate,
            device=self.device,
            channels=self.channels,
            dtype=self.dtype,
        ) as stream:
            while True:
                chunk = self._q.get()
                if chunk is None:
                    break
                stream.write(chunk)

    def feed(self, audio):
        self._q.put(audio)

    def stop(self):
        self._q.put(None)
        if self._thread:
            self._thread.join()
