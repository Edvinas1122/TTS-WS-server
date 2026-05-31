#!/usr/bin/env python3
"""WebSocket TTS streaming server."""

import asyncio
import os
import sys

import websockets

from src.handler import handle_client
from src.model import load_engine, create_session, load_voices_config, get_default_voice


import config


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, base)

    engine = load_engine(
        config.get("model_path"),
        verbose=config.get("verbose"),
    )

    voices = load_voices_config()
    default_voice = get_default_voice(voices)
    if not default_voice:
        print("No voices found in voices/config.json", flush=True)
        return

    port = config.get("ws_port")

    async def serve():
        async with websockets.serve(
            lambda ws: handle_client(
                ws,
                create_session(engine, default_voice),
                verbose=config.get("verbose"),
            ),
            "0.0.0.0", port,
        ):
            print(f"TTS server on ws://0.0.0.0:{port}")
            print(f"Default voice: {default_voice['name']} ({len(voices)} available)", flush=True)
            await asyncio.Future()

    asyncio.run(serve())


if __name__ == "__main__":
    main()
