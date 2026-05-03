import { useState } from 'react';

export default function TextTab({ onSend }) {
  const [text, setText] = useState('');
  const [color, setColor] = useState('#ff7a00');
  const [speed, setSpeed] = useState(225);

  const send = () => {
    if (!text.trim()) return;
    const hex = color.startsWith('#') ? color.slice(1) : color;
    const cmd = { kind: 'text', text, speed };
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
        <label className="field-label">Text ({text.length}/64)</label>
        <textarea maxLength={64} value={text} onChange={(e) => setText(e.target.value)} className="textarea" rows={2} />
      </div>
      <div>
        <label className="field-label">Color</label>
        <input className="input" value={color} onChange={(e) => setColor(e.target.value)} />
      </div>
      <div className="slider-group">
        <div className="slider-header"><span>Speed</span><span>{speed}</span></div>
        <input type="range" min={32} max={240} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="slider" />
      </div>
      <button className="btn btn-primary" onClick={send}>Send text</button>
    </div>
  );
}
