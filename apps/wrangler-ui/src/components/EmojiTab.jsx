import { useEffect, useState } from 'react';
import { api } from '../api.js';

function resolveEmojiCommand(glyph) {
  const table = {
    '🔥': { kind: 'effect', name: 'fire' },
    '🌈': { kind: 'effect', name: 'rainbow' },
    '⚡': { kind: 'effect', name: 'sparkle', speed: 220 },
    '🎉': { kind: 'effect', name: 'fireworks' },
    '🐍': { kind: 'preset', name: 'snake_attack' },
    '💥': { kind: 'preset', name: 'crowd_hype' },
    '🤠': { kind: 'preset', name: 'howdy' },
    '⭐': { kind: 'preset', name: 'lone_star' },
    '🌙': { kind: 'preset', name: 'late_night' },
    '🌊': { kind: 'preset', name: 'sine_wave' },
    '❤️': { kind: 'color', color: { r: 255, g: 0, b: 0 } },
    '💙': { kind: 'color', color: { r: 0, g: 0, b: 255 } },
    '💚': { kind: 'color', color: { r: 0, g: 200, b: 0 } },
    '💜': { kind: 'color', color: { r: 180, g: 0, b: 255 } },
    '🧡': { kind: 'color', color: { r: 255, g: 100, b: 0 } },
    '🖤': { kind: 'power', on: false },
  };
  return table[glyph] || null;
}

export default function EmojiTab({ onSend }) {
  const [labels, setLabels] = useState({});
  useEffect(() => { api.listEmoji().then((d) => setLabels(d.emoji)).catch(() => {}); }, []);
  const glyphs = Object.keys(labels);
  return (
    <div className="emoji-grid">
      {glyphs.map((g) => {
        const cmd = resolveEmojiCommand(g);
        if (!cmd) return null;
        return (
          <button key={g} className="emoji-chip" onClick={() => onSend(cmd)} title={labels[g]}>
            <span className="emoji-glyph">{g}</span>
            <span className="emoji-label">{labels[g]}</span>
          </button>
        );
      })}
    </div>
  );
}
