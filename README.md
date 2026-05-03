# WrangLED Fast-Track Dashboard

WrangLED is a highly-interactive build log and project management dashboard for the PyTexas 2025 conference (April 17–19, 2026 at the Austin Central Library). This project tracks the build of an IoT LED Matrix that virtual attendees can control via Discord commands.

This React application was built using Vite and currently acts as the Command Center for our 6-day sprint.

## The Story So Far

*One community, twelve months of building toward April.*

- **May 2025**: Jesse is humbled to serve as the Community Committee Chair for PyTexas.
- **Oct 2025**: AI Night concept is born after Jeff Triplett's RAG talk gathers 68 attendees!
- **Jan 202**: PyTexas AI Night launches as a monthly virtual lightning talk series on Discord.
- **Feb 2026**: Jesse commits full-time to PyTexas & Per Scholas.
- **Mar 25, 2026**: Jim (CowboyQuant) presents Lumbergh at AI Night. The talk goes down as the "Talk of the season 🏆".
-**Apr 02. 2026**: The WrangLED concept is born at the DFW Pythoneers Meetup in Plano.
- **Apr 6, 2026**: Hardware arrives. The first LED panel lights up in the kitchen at 2:17 AM 🔥.
- **Apr 17–19, 2026**: PyTexas 2026.

### WrangLED Origin Story

*"What if virtual attendees could control the LEDs?"*

Following AI Night, Jesse and Jim connected and evolving a YouTube collaboration idea into building a live interactive piece for PyTexas. The timeline? Barely a week. 
The team ordered the hardware (Pi 4, SP803E, BTF 8x32 matrix), and Jim joined up via Tailscale to start building the Discord-to-WLED pipeline remotely while Jesse wired the 256 LEDs to the 20A PSU.

## Hardware Note & Troubleshooting

![WrangLED Dual Panels](./public/both_panels_lit.jpg) 
*(Note: Be sure to save the latest dual-panel photo to the `public/` directory as `both_panels_lit.jpg`)*

> [!WARNING] 
> **Friendly reminder to check the simple parts before digging too deep.** During our late-night wiring session, only one panel lit up at first because the WLED software settings were set to a single panel instead of two! Always verify software matrix/strip lengths before re-checking your data lines.

## The People Making It Happen

- **Jesse Flippen** (Community Committee Chair): Founded AI Night, structured WrangLED hardware, and managed conference logistics.
- **Jim / CowboyQuant** (Software Lead): Created the FastAPI + WebSocket architecture, Lumbergh creator.
- **Kevin** (Discord Bot Engineer): Handled bottom deployment on Mason's VPS and integration with Jim's FastAPI.
- **Mason Egger** (PyTexas President): Conference coordination, VPS host, and Monday deadline enforcer.

WrangLED isn't just a hardware project. It's what happens when the Python community builds something together: Open-source, built live, and bridging the gap between virtual and in-person attendees.
