import base64
import functools
import io
import json
import sys
import time

import numpy as np
import scipy.io.wavfile as wav


def encode_chunk(audio, sample_rate):
    buf = io.BytesIO()
    wav.write(buf, sample_rate, np.array(audio))
    return base64.b64encode(buf.getvalue()).decode()


async def stream_readable_to_socket(websocket, session, text, lang_code=None, stop_event=None, on_send=None, on_done=None):
    seq = 0

    async for chunk in session.generate_async(text, lang_code=lang_code):
        if stop_event and stop_event.is_set():
            break
        b64 = encode_chunk(chunk["audio"], chunk["sample_rate"])
        await websocket.send(json.dumps({
            "type": "audio", "data": b64, "sample_rate": chunk["sample_rate"], "seq": seq,
        }))
        if on_send:
            on_send(seq=seq, chunk=chunk)
        seq += 1

    if stop_event and stop_event.is_set():
        await websocket.send(json.dumps({"type": "stopped", "chunks": seq}))
    else:
        await websocket.send(json.dumps({"type": "done", "chunks": seq}))

    if on_done:
        on_done(seq=seq, stopped=bool(stop_event and stop_event.is_set()))


def verbose(info):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(websocket, session, text, lang_code=None, stop_event=None):
            info("request", text=text[:60])

            def on_send(*, seq, chunk):
                dur = len(np.array(chunk["audio"])) / chunk["sample_rate"]
                info("chunk", seq=seq, duration=dur)

            def on_done(*, seq, stopped):
                info("done", chunks=seq)

            await func(websocket, session, text, lang_code=lang_code, stop_event=stop_event, on_send=on_send, on_done=on_done)

        return wrapper
    return decorator


def stderr_logger(phase, **data):
    t = time.time()
    if phase == "request":
        print(f"[{t:.1f}] text='{data['text']}'", file=sys.stderr, flush=True)
    elif phase == "chunk":
        print(f"  chunk {data['seq']}: {data['duration']:.2f}s", file=sys.stderr, flush=True)
    elif phase == "done":
        label = "Stopped" if data.get("stopped") else "Done"
        print(f"[{t:.1f}] {label}, {data['chunks']} chunks", file=sys.stderr, flush=True)
