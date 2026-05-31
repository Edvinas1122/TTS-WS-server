# Voice TTS

[![GitHub](https://img.shields.io/badge/GitHub-Edvinas1122/TTS--WS--server-181717?logo=github)](https://github.com/Edvinas1122/TTS-WS-server)

CUDA-accelerated WebSocket TTS streaming server.

**Model**: [Qwen/Qwen3-TTS-12Hz-0.6B-Base](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base) via `faster-qwen3-tts`

## Start

```bash
cd ~/Documents/code/TTS && ~/torch-env/bin/python server.py
```

Listens on `ws://0.0.0.0:8765`.

## Model lifetime — 3 stages

| Stage | Scope | What |
|---|---|---|
| **Engine** | Program | `FasterQwen3TTS.from_pretrained()` — loaded once, 4 GB VRAM |
| **Session** | Connection | Holds `{voice, lang, speed}` per WS client. Created on connect, configurable via `configure` |
| **Generate** | Request | `session.generate(text)` — streams audio chunks immediately using the session's voice/lang |

## WebSocket API

### Client → Server

| Type | Fields | Description |
|---|---|---|
| `voices` | — | List available voices |
| `configure` | `voice?`, `lang?`, `speed?` | Set session defaults |
| `synthesize` | `text`, `id?`, `voice?`, `lang?` | Start TTS stream. `voice`/`lang` override session for this request |
| `stop` | `id` | Cancel a running synthesize |

### Server → Client

| Type | Fields | Description |
|---|---|---|
| `error` | `message` | Error response |
| `voices` | `voices: [{name, description, languages}]` | Voice catalog |
| `configured` | `voice, lang, speed` | Confirms session change |
| `started` | `id` | Synthesize accepted, streaming begins |
| `audio` | `data: base64_wav, sample_rate, seq` | One audio chunk |
| `done` | `chunks` | Stream completed |
| `stopped` | `chunks`, `id?` | Stream cancelled (by `stop` or mid-stream break) |

## Example flow

```
→ {"type":"configure", "voice":"ref_voice", "lang":"zh"}
← {"type":"configured", "voice":"...", "lang":"chinese", "speed":1.0}
→ {"type":"synthesize", "text":"你好", "id":"req-1"}
← {"type":"started", "id":"req-1"}
← {"type":"audio", "data":"...", "sample_rate":24000, "seq":0}
← {"type":"audio", "data":"...", "sample_rate":24000, "seq":1}
← {"type":"done", "chunks":12}
```

## Voices

Defined in `voices/config.json`. Voice = timbre (from `.wav`), language = generation language — independent.

```json
{"name": "my_voice", "description": "...", "languages": ["en", "zh"]}
```

Add: place `voices/my_voice.wav` + `voices/my_voice.txt`, add entry to `config.json`.

## Config

`config.json` — server settings only (no voice defaults; default voice is marked in `voices/config.json`).

| Key | Default | Description |
|---|---|---|---|
| `ws_port` | 8765 | Listen port |
| `model_path` | Qwen/Qwen3-TTS-12Hz-0.6B-Base | HF model ID or local path |
| `verbose` | false | Log chunks to stderr |
| `device` | null | CUDA device (null = auto) |

## Quick test

```bash
~/torch-env/bin/python -c "
import asyncio, websockets, json
async def t():
    async with websockets.connect('ws://localhost:8765') as ws:
        await ws.send(json.dumps({'type':'synthesize', 'text':'Hello!'}))
        async for m in ws:
            d = json.loads(m)
            if d['type'] == 'audio': print(f'chunk {d[\"seq\"]}')
            elif d['type'] == 'done': print('done'); break
asyncio.run(t())
"
```
