---
theme: seriph
background: /img/title-bg.png
title: WrangLED
info: |
  5-minute lightning talk · PyTexas 2026
class: text-center
highlighter: shiki
transition: slide-left
mdc: true
fonts:
  sans: 'Inter'
  mono: 'JetBrains Mono'
---

<div class="absolute inset-0 bg-black/70"></div>

<div class="relative z-10 pt-6">

# Before I start — open your phone.

<div class="pt-4 text-3xl">
PyTexas Discord → type <code>/led text hello</code>
</div>

<div class="pt-4 text-lg opacity-85">
The matrix behind me is already listening.<br/>
Send anything. I'll wait.
</div>

<div class="pt-8 flex items-center justify-center gap-8">
  <img src="/img/qr-discord.png" class="w-40 h-40 rounded-lg bg-white p-2"/>
  <div class="text-left">
    <div class="text-xl opacity-90">Scan → PyTexas Discord</div>
    <div class="text-sm opacity-70">discord.gg/mH7Fb9HE</div>
  </div>
</div>

<div class="pt-6 text-sm opacity-70 italic">
(Yes, strangers get to heckle me for the next 5 minutes. That's the point.)
</div>

</div>

---
layout: default
background: /img/title-bg.png
class: text-white text-center
---

<div class="absolute inset-0 bg-black/70"></div>

<div class="relative z-10">

# WrangLED

## We built a Discord-controlled LED matrix in 8 days.
## Most of it worked.

<div class="pt-8 flex items-center justify-center gap-4">
  <img src="/img/cowboyquant.png" class="w-14 h-14 rounded-full"/>
  <div class="text-left">
    <div class="text-lg"><b>Jim Vogel</b> — <code>@CowboyQuant</code> on Discord</div>
    <div class="text-sm opacity-80">w/ Jesse Flippen · PyTexas 2026</div>
  </div>
</div>

</div>

---
layout: image-right
image: /img/conference.jpg
class: !text-left
---

# The ask

> *"What if virtual attendees could **heckle us** with the LEDs?"*

<div class="pt-4 space-y-2">

- **Apr 2** — idea sparked at the DFW Pythoneers meetup
- **Apr 6** — hardware arrives in a flurry of Amazon boxes
- **Apr 17** — demo on stage at PyTexas

</div>

<div class="pt-6 opacity-70 italic">
Fifteen days. No pressure.
</div>

---
layout: image
image: /img/hero-panels.jpg
class: text-white
---

<div class="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-transparent"></div>

<div class="absolute bottom-10 left-10 right-10">

# First light 🔥

<div class="text-xl opacity-90">
2:17 AM. A kitchen table somewhere in DFW. The PSU held.
</div>

<div class="pt-3 text-base opacity-75">
Only one panel lit up. <i>"Must be your wiring."</i> &nbsp;Reader, it was a config flag.
</div>

</div>

---
layout: image-left
image: /img/build-night.png
class: !text-left
---

# Two Pythonistas. One Discord server.

<div class="pt-2 space-y-2 text-sm">

- Met **once** — at the DFW Pythoneers meetup where this idea was born
- Built the **entire project** over Discord. No calls. No meetings. Just chat.
- Two kitchens. Two soldering irons. Two separate rigs.
- Day jobs by day. Pi hacking by night.

</div>

<div class="pt-5 text-base opacity-90 italic">
In theory, both rigs worked.
</div>

---
layout: default
background: /img/architecture-bg.png
class: text-white
---

<div class="absolute inset-0 bg-black/60"></div>

<div class="relative z-10">

# Architecture

```mermaid {scale: 0.85}
flowchart LR
  D[Discord bot] --> API
  UI[Dashboard PWA] --> API
  API[FastAPI hub<br/>command bus] -- WebSocket --> W[wrangler on Pi<br/>outbound only]
  W -- HTTP --> L1[WLED panel 1]
  W -- HTTP --> L2[WLED panel 2]
  W -- HTTP --> L3[WLED panel 3]
  API -. SSE .-> UI
```

<v-clicks>

- **Three moving parts:** WLED firmware · `wrangler` on the Pi · `api` hub.
- **The Pi dials home.** Opening a port on conference Wi-Fi is a dare, not a plan.
- **🏆 Contracts decided up front paid for themselves every single day.**

</v-clicks>

</div>

---
layout: image-right
image: /img/numbers-bg.png
class: !text-left
---

# The numbers & the scars

<div class="pt-2 space-y-2">

- **8 days · 165 commits · 3 panels · 0 face-to-face meetings**
- **70 commits on a single Monday.** *I have a day job. Allegedly.*
- 🛑 **`/panic`** — shipped ~4 min after a stranger discovered `/led text`
- 🤖 **Discord's 25-choice limit** — autocomplete, deployed live
- 📡 **Retry-on-Wi-Fi-chaos** — conference halls hate TCP
- 🧵 **Async fan-out** — one thread can't serve Discord *and* three WLEDs

</div>

---
layout: image-left
image: /img/friday-morning.png
class: !text-left
---

# Friday, 9 AM. Same room, finally.

<div class="pt-2 space-y-2 text-sm">

- First time in the **same room** working on this thing
- The handshake included a **screwdriver**
- Two rigs + one deployment = **frantic config**
- Conference Wi-Fi: round one
- Time pressure turns every bug into a 10-minute bug

</div>

<div class="pt-5 text-lg italic opacity-90">
"In theory, both rigs worked."
</div>
<div class="text-sm opacity-70">
— me, 8 hours before this talk, lying confidently
</div>

---
layout: image
image: /img/thanks-bg.png
class: text-white text-center
---

<div class="absolute inset-0 bg-black/70"></div>

<div class="relative z-10 pt-10">

# Try it. Right now.

<div class="pt-4 text-3xl">
PyTexas Discord → type <code>/led text</code> anything
</div>

<div class="pt-3 text-lg opacity-80">
The matrix is behind me. It's watching.
</div>

<div class="pt-8 flex items-center justify-center gap-10">
  <div class="flex items-center gap-4">
    <img src="/img/cowboyquant.png" class="w-24 h-24 rounded-full"/>
    <div class="text-left">
      <div class="text-xl">Find me: <code>@CowboyQuant</code></div>
      <div class="text-base opacity-80">green cowboy logo</div>
    </div>
  </div>
  <div class="flex items-center gap-3">
    <img src="/img/qr-repo.png" class="w-28 h-28 rounded-lg bg-white p-1"/>
    <div class="text-left">
      <div class="text-xl">The code</div>
      <div class="text-base opacity-80">github.com/JesseFlip/<br/>wrangled-dashboard</div>
    </div>
  </div>
</div>

<div class="pt-6 text-base">
Thanks <b>Jesse</b> 👋 · the PyTexas crew · everyone pointing an LED at me right now.
</div>

</div>
