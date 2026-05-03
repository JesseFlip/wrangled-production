import json
from wrangled_contracts import PresetCommand, PRESETS
from wrangler.pusher import _build_preset_bodies

def debug_preset(name):
    cmd = PresetCommand(name=name)
    bodies = _build_preset_bodies(cmd)
    print(f"Preset: {name}")
    for i, body in enumerate(bodies):
        print(f"  Body {i}: {json.dumps(body, indent=2)}")

if __name__ == "__main__":
    try:
        debug_preset("love_it")
    except Exception as e:
        print(f"Error: {e}")
