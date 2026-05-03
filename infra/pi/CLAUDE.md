# infra/pi — Raspberry Pi Deployment Assets

## Status
**Not yet implemented.** Placeholder for milestone 1.

## Intended contents
- `wrangler.service` — systemd unit running `uv run wrangler run` on boot
- `install.sh` — first-time setup (apt prereqs, uv install, clone, enable service)
- `update.sh` — pull + restart
