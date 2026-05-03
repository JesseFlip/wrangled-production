import { useEffect, useState } from 'react';
import { api } from '../api.js';

export default function EffectTab({ onSend }) {
  const [effects, setEffects] = useState([]);
  const [name, setName] = useState('rainbow');
  const [speed, setSpeed] = useState(128);
  const [intensity, setIntensity] = useState(128);
  const [color, setColor] = useState('');

  useEffect(() => { api.listEffects().then((d) => setEffects(d.effects)).catch(() => {}); }, []);

  const send = () => {
    const cmd = { kind: 'effect', name, speed, intensity };
    if (color.trim()) {
      const hex = color.startsWith('#') ? color.slice(1) : color;
      if (hex.length === 6) {
        cmd.color = {
          r: parseInt(hex.slice(0, 2), 16),
          g: parseInt(hex.slice(2, 4), 16),
          b: parseInt(hex.slice(4, 6), 16),
        };
      }
    }
    onSend(cmd);
  };

  return (
    <div className="stack">
      <div>
        <label className="field-label">Effect</label>
        <select className="select" value={name} onChange={(e) => setName(e.target.value)}>
          {effects.map((e) => (<option key={e} value={e}>{e}</option>))}
        </select>
      </div>
      <div className="slider-group">
        <div className="slider-header"><span>Speed</span><span>{speed}</span></div>
        <input type="range" min={0} max={255} value={speed} onChange={(e) => setSpeed(Number(e.target.value))} className="slider" />
      </div>
      <div className="slider-group">
        <div className="slider-header"><span>Intensity</span><span>{intensity}</span></div>
        <input type="range" min={0} max={255} value={intensity} onChange={(e) => setIntensity(Number(e.target.value))} className="slider" />
      </div>
      <div>
        <label className="field-label">Color (optional, #hex)</label>
        <input className="input" value={color} onChange={(e) => setColor(e.target.value)} placeholder="#ff7a00" />
      </div>
      <button className="btn btn-primary" onClick={send}>Fire effect 🔥</button>
    </div>
  );
}
