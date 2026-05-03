import { useEffect, useState } from 'react';
import { api } from '../api.js';

const PRESET_GRADIENTS = {
  pytexas: 'linear-gradient(135deg, #ff7a00, #ffc43b)',
  party: 'linear-gradient(135deg, #b54cff, #ff4fa4)',
  chill: 'linear-gradient(135deg, #1a4dff, #1fbde6)',
};

export default function PresetTab({ onSend }) {
  const [presets, setPresets] = useState([]);
  useEffect(() => { api.listPresets().then((d) => setPresets(d.presets)).catch(() => {}); }, []);
  return (
    <div className="preset-grid">
      {presets.map((name) => (
        <button
          key={name}
          className="preset-card"
          style={{ backgroundImage: PRESET_GRADIENTS[name] }}
          onClick={() => onSend({ kind: 'preset', name })}
        >
          {name}
        </button>
      ))}
    </div>
  );
}
