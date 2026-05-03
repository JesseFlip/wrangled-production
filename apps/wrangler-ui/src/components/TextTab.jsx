import { useState } from 'react';

export default function TextTab({ onSend }) {
  const [text, setText] = useState('');
  const [color, setColor] = useState('#ff7a00');
<<<<<<< HEAD
  const [speed, setSpeed] = useState(20);
=======
  const [speed, setSpeed] = useState(225);
>>>>>>> 5334bf1b39749b1aaf4a365d2ecea784df29a418
  const [intensity, setIntensity] = useState(128);

  const send = () => {
    if (!text.trim()) return;
    const hex = color.startsWith('#') ? color.slice(1) : color;
    const cmd = { kind: 'text', text, speed, intensity };
    if (hex.length === 6) {
      cmd.color = {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16),
      };
    }
    onSend(cmd);
  };

  return (
    <div className="stack">
      <div>
        <div className="card-header" style={{ marginBottom: 'var(--sp-1)', padding: 0 }}>
          <span>Message ({text.length}/64)</span>
        </div>
        <textarea
          maxLength={64}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Enter text to display..."
          className="textarea"
          rows={2}
        />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--sp-4)' }}>
        <div>
          <label className="field-label">Color</label>
          <div className="color-input-group">
            <input
              type="color"
              className="input-color"
              value={color}
              onChange={(e) => setColor(e.target.value)}
            />
            <input
              className="input-hex"
              value={color}
              onChange={(e) => setColor(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--sp-6)' }}>
        <div className="slider-group">
          <div className="slider-header">
            <span>Scroll Speed</span>
            <span>{speed}</span>
          </div>
          <input
            type="range"
            min={1}
            max={255}
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            className="slider"
          />
        </div>

        <div className="slider-group">
          <div className="slider-header">
            <span>Vertical Offset</span>
            <span>{intensity === 128 ? 'Centered (128)' : intensity}</span>
          </div>
          <input
            type="range"
            min={0}
            max={255}
            value={intensity}
            onChange={(e) => setIntensity(Number(e.target.value))}
            className="slider"
          />
        </div>
      </div>

      <button
        className="btn btn-primary"
        style={{ width: '100%', padding: 'var(--sp-4)', marginTop: 'var(--sp-2)' }}
        onClick={send}
        disabled={!text.trim()}
      >
        Push to Matrix
      </button>
    </div>
  );
}
