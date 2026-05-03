# Mobile Conference UI Redesign

**Date:** 2026-04-16
**Context:** PyTexas conference — operator needs a phone-first dashboard for monitoring, moderating, and controlling WLEDs from the booth.

## Problem

The current dashboard splits Control and Mod into separate pages with a desktop-oriented layout. At the conference, the operator (single person) needs to monitor Discord commands, ban bad actors, push content to LEDs, and demo effects — all one-handed on a phone.

## Design: Bottom-Tab Mobile App

Three thumb-reachable tabs with a persistent global bar. Installable as a PWA for full-screen, app-like experience.

### Global Bar (Always Visible)

Pinned to the top on every tab:

- **Status line:** Device count, Discord connection status, red KILL switch (emergency off — powers down all devices and pauses Discord bot), gear icon for settings (opens a slide-up sheet with bot config: preset-only mode, brightness cap, cooldown, device locks).
- **Target group pills:** Tap to select which device group receives commands. "All" is the default. Groups are configurable (e.g., "Discord", "Stage").
- **Brightness slider:** Global brightness override, always accessible.
- **Color dot:** Tap to open a quick color picker. This is the "paintbrush" — sets the color used by subsequent commands (text, effects, etc.) until changed. The dot reflects the current color.

### Tab 1: Stream (The Bouncer View)

Live feed of every command hitting the LEDs. This is the primary screen during the conference.

**Message cards** show:
- Username, timestamp, command content (actual text for text commands, preset name for presets, etc.)
- Source and target group
- Ban button on every message (subtle for normal, prominent for flagged)

**Flagged messages** are visually distinct:
- Red border, highlighted username, reason label ("Rate limit exceeded", "Blocked content")
- Large BAN button — one tap and the user is banned
- Blocked text is blurred but readable for verification

**Behavior:**
- Auto-scrolls to newest messages
- Pauses auto-scroll when user scrolls up to review history
- Operator's own commands (from Command/Toolkit tabs) also appear in the stream

### Tab 2: Command (The Daily Driver)

The 90% use case — presets, schedule, and custom text.

**Layout top to bottom:**

1. **Now Playing / Up Next** — Auto-updates from the conference schedule. Each talk card has a PUSH button that sends talk title + speaker as scrolling text to the target group.

2. **Quick Text** — Text input + send button. Canned message chips below for common phrases ("Break til 3pm", "Welcome!", "Thanks for coming"). Canned messages are configurable. Text uses the global color from the top bar.

3. **Presets** — Grid of large tappable gradient buttons (pytexas, party, chill, fire, matrix, off). One tap fires immediately to the target group.

4. **Matrix Mode** — Toggle buttons for idle/clock/schedule/countdown. Countdown shows an inline time picker when selected.

### Tab 3: Toolkit (The Show-Off Tab)

Full control surface for demos and power-user needs.

**Sections:**

1. **Colors** — Grid of color swatches + hex input. Tapping a color sends it to the target group AND updates the global color override (top bar dot syncs). Double duty for fast demos.

2. **Effects** — Dropdown effect picker, speed slider (0-255), intensity slider (0-255), "Fire Effect" button. The demo surface when someone asks "what is this?"

3. **Emoji** — One-tap grid of emoji, fires immediately to target group.

4. **Devices** — Compact status list (name, on/off indicator). Rescan button. Tap info icon for details (IP, dimensions, MAC). Troubleshooting only, not the primary workflow.

## Backend Changes

### Device Groups

New concept: named groups of devices.

- A group is a name mapped to a list of device MACs.
- Stored and managed via the API (CRUD endpoints).
- "All" is a built-in group that always targets every connected device.
- All command endpoints accept a `group` parameter. When provided, the command is broadcast to every device in that group.
- Groups are configured before the conference and selected via the target group pills in the UI.

### Command Stream Endpoint

New real-time endpoint (SSE or WebSocket) that pushes every command as it occurs.

Each event includes:
- Timestamp
- Source (Discord username/ID, operator, system)
- Command type (text, color, effect, preset, emoji, power, etc.)
- Command content (the actual text, color value, preset name, etc.)
- Target group
- Result (ok, blocked, failed)
- Flag status (none, rate_limited, content_blocked) with reason

This replaces the polling-based command history in the current ModView.

### Content Filtering

Server-side profanity filter using `better-profanity` Python library.

- Runs synchronously on every text command before it reaches the LEDs.
- Blocked messages never hit the devices.
- Blocked messages appear in the command stream with `result: "blocked"` and `flag: "content_blocked"` so the operator sees them and can ban the sender.
- Custom words can be added to the blocklist via configuration.

### Rate Limiting

Per-user rate counter for Discord commands.

- If a user exceeds N commands/minute (configurable, existing `cooldown_seconds` config), subsequent messages are still delivered to the LEDs but flagged in the stream.
- Rate-limited messages are delivered and flagged — not auto-blocked and not auto-banned. The operator decides from the stream.
- The stream shows the rate (e.g., "12 msgs/min") on flagged messages.

### PWA Support

- Add `vite-plugin-pwa` to the dashboard build.
- Manifest with `display: standalone`, app name, icons.
- Service worker caches the app shell (HTML, JS, CSS, static assets).
- API calls still require connectivity — no offline data caching.
- Result: installable to home screen, runs full-screen without browser chrome.

## What Gets Removed / Replaced

The current three-page layout (Control, Mod, Story) is replaced by the three-tab mobile layout. Specifically:

- **Control page** → Split between Command tab (presets, schedule, text, modes) and Toolkit tab (colors, effects, emoji, devices).
- **Mod page** → Absorbed into the Stream tab (banning, command monitoring) and the global bar (emergency off, bot controls). Device locks and bot config (preset-only mode, brightness cap, cooldown) move to a settings sheet accessible from the global bar.
- **Story page** → Removed from the mobile UI. It's a build log, not an operator tool. Can remain accessible at `#/about` for desktop but is not in the mobile tab bar.

## What Stays the Same

- Auth gate (token prompt) — unchanged.
- All existing API endpoints — the new UI calls the same endpoints, plus the new ones (groups, stream, content filter).
- The API still serves built static assets — the new dashboard replaces the old one.
- Desktop access still works — the mobile-first layout works fine on desktop too (max-width container or responsive breakpoints).

## Out of Scope

- LLM-based content moderation (future enhancement — llama3.2 via ollama for catching leetspeak/evasion)
- Group management UI (groups are configured via API/config before the conference)
- Offline mode beyond app shell caching
- Story/build-log page redesign
