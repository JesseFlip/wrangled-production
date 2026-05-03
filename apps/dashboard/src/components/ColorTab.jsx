import { useState } from 'react';

const NAMED = [
  ['red', [255, 0, 0]], ['orange', [255, 100, 0]], ['yellow', [255, 220, 0]],
  ['green', [0, 200, 0]], ['cyan', [0, 200, 200]], ['blue', [0, 0, 255]],
  ['purple', [180, 0, 255]], ['pink', [255, 120, 180]], ['white', [255, 255, 255]],
  ['black', [0, 0, 0]],
];

function parseHex(h) {
  const s = h.replace('#', '');
  if (s.length === 3) return [0, 1, 2].map((i) => parseInt(s[i] + s[i], 16));
  if (s.length === 6) return [0, 2, 4].map((i) => parseInt(s.slice(i, i + 2), 16));
  return null;
}

export default function ColorTab({ onSend }) {
  const [hex, setHex] = useState('#ff7a00');

  const sendRgb = ([r, g, b]) => onSend({ kind: 'color', color: { r, g, b } });

  const sendHex = () => {
    const rgb = parseHex(hex);
    if (rgb) sendRgb(rgb);
  };

  return (
    <div className="stack">
      <div className="color-grid">
        {NAMED.map(([name, rgb]) => (
          <button
            key={name}
            type="button"
            className="color-chip"
            style={{ background: `rgb(${rgb.join(',')})` }}
            onClick={() => sendRgb(rgb)}
            title={name}
          >
            <span className="color-chip-label">{name}</span>
          </button>
        ))}
      </div>
      <div className="color-hex-row">
        <label className="field-label" htmlFor="hex">Hex</label>
        <input id="hex" className="input" value={hex} onChange={(e) => setHex(e.target.value)} />
        <span className="color-hex-preview" style={{ background: hex }} />
        <button className="btn btn-primary" onClick={sendHex}>Send</button>
      </div>
    </div>
  );
}
