"""Load config.json from this directory. Keys are accessible via get()."""

import json
import os

_path = os.path.dirname(os.path.abspath(__file__))
_cfg = {}
_cfg_path = os.path.join(_path, "config.json")
if os.path.exists(_cfg_path):
    with open(_cfg_path) as f:
        _cfg = json.load(f)


def get(key, default=None):
    return _cfg.get(key, default)
