#!/usr/bin/env python3
"""Read options as JSON from stdin, generate TTS, print result as JSON."""
import json, sys, os
import mlx.core as mx
from mlx_audio.tts.utils import load_model
from mlx_audio.audio_io import write as audio_write

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

opts = json.loads(sys.stdin.read())
model_path = os.environ.get("TTS_MODEL_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), config.get("model_path", "models/base")))

model = load_model(model_path)
os.makedirs(opts["outputDir"], exist_ok=True)

results = model.generate(
    text=opts["text"],
    voice=opts.get("voice", "serena"),
    lang_code=opts.get("lang", "en"),
    speed=opts.get("speed", 1.0),
    verbose=False,
)

for i, result in enumerate(results):
    file_path = os.path.join(opts["outputDir"], f"{opts['prefix']}_{i:03d}.wav")
    audio_write(file_path, result.audio, result.sample_rate, format="wav")

    info = {
        "file": file_path,
        "duration": result.audio_duration,
        "samples": result.audio_samples["samples"],
        "sample_rate": result.audio_samples["samples-per-sec"],
    }

# Print last result info
print(json.dumps(info))
