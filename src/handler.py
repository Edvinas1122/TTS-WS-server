import asyncio
import json
import sys
import time

from src.stream import stream_readable_to_socket, stderr_logger, verbose as verbose_wrap
from src.model import load_voices_config

_tasks: dict[str, tuple[asyncio.Task, asyncio.Event]] = {}
_conn_tasks: dict[int, set[str]] = {}


async def handle_client(websocket, session, verbose=False):
    peer = websocket.remote_address
    conn_id = id(websocket)
    _conn_tasks[conn_id] = set()
    t = time.time()
    print(f"[{t:.1f}] CONNECT {peer}", file=sys.stderr, flush=True)
    voices = load_voices_config()

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as e:
                await websocket.send(json.dumps({"type": "error", "message": f"invalid JSON: {e}"}))
                continue

            cmd = msg.get("type")

            if cmd == "voices":
                await websocket.send(json.dumps({
                    "type": "voices",
                    "voices": [
                        {"name": v["name"], "description": v.get("description", ""),
                         "languages": v.get("languages", [])}
                        for v in voices
                    ],
                }))
            elif cmd == "configure":
                await _handle_configure(websocket, session, msg)
            elif cmd == "synthesize":
                await _handle_synthesize(websocket, session, msg, verbose, conn_id)
            elif cmd == "stop":
                await _handle_stop(websocket, msg)
            else:
                await websocket.send(json.dumps({"type": "error", "message": f"unknown command: {cmd}"}))
    except Exception as e:
        t = time.time()
        print(f"[{t:.1f}] ERROR {peer}: {e}", file=sys.stderr, flush=True)
    finally:
        t = time.time()
        print(f"[{t:.1f}] DISCONNECT {peer}", file=sys.stderr, flush=True)
        for tid in _conn_tasks.pop(conn_id, set()):
            entry = _tasks.pop(tid, None)
            if entry:
                task, stop_event = entry
                stop_event.set()
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


async def _handle_configure(websocket, session, msg):
    try:
        session.configure(
            voice=msg.get("voice"),
            lang=msg.get("lang"),
            speed=msg.get("speed"),
        )
        await websocket.send(json.dumps({
            "type": "configured",
            "voice": session.ref_audio,
            "lang": session.lang,
            "speed": session.speed,
        }))
    except ValueError as e:
        await websocket.send(json.dumps({"type": "error", "message": str(e)}))


async def _handle_synthesize(websocket, session, msg, verbose, conn_id):
    text = msg.get("text", "").strip()
    if not text:
        await websocket.send(json.dumps({"type": "error", "message": "text is required"}))
        return

    task_id = msg.get("id", str(id(msg)))
    stop_event = asyncio.Event()

    voice = msg.get("voice")
    lang_code = msg.get("lang")
    if voice or lang_code:
        try:
            session.configure(voice=voice, lang=lang_code)
        except ValueError as e:
            await websocket.send(json.dumps({"type": "error", "message": str(e)}))
            return

    stream_fn = stream_readable_to_socket
    if verbose:
        stream_fn = verbose_wrap(stderr_logger)(stream_readable_to_socket)

    async def stream():
        try:
            await stream_fn(websocket, session, text, lang_code=lang_code, stop_event=stop_event)
        finally:
            _tasks.pop(task_id, None)
            _conn_tasks.get(conn_id, set()).discard(task_id)

    task = asyncio.create_task(stream())
    _tasks[task_id] = (task, stop_event)
    _conn_tasks[conn_id].add(task_id)
    await websocket.send(json.dumps({"type": "started", "id": task_id}))


async def _handle_stop(websocket, msg):
    task_id = msg.get("id")
    if not task_id:
        await websocket.send(json.dumps({"type": "error", "message": "id is required"}))
        return

    entry = _tasks.pop(task_id, None)
    if entry:
        task, stop_event = entry
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await websocket.send(json.dumps({"type": "stopped", "id": task_id}))
