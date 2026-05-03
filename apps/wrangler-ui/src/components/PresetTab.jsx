import { useEffect, useState } from 'react';
import { api } from '../api.js';

const PRESET_GRADIENTS = {
  pytexas: 'linear-gradient(135deg, #ff7a00, #ffc43b)',
  party: 'linear-gradient(135deg, #b54cff, #ff4fa4)',
  chill: 'linear-gradient(135deg, #1a4dff, #1fbde6)',
  howdy: 'linear-gradient(135deg, #ff7a00, #e6b800)',
  breaktime: 'linear-gradient(135deg, #00c6ff, #0072ff)',
  networking: 'linear-gradient(135deg, #8e2de2, #4a00e0)',
};

export default function PresetTab({ onSend }) {
  const [presets, setPresets] = useState([]);
  const [selected, setSelected] = useState(null);
  const [speedOverride, setSpeedOverride] = useState(null);

  useEffect(() => {
    api.listPresets()
      .then((d) => setPresets(d.presets))
      .catch(() => {});
  }, []);

  const handlePush = (name) => {
    // Only include speed_override in the payload if the user has
    // explicitly set it — sending null causes a Pydantic 422 error.
    const cmd = { kind: 'preset', name };
    if (speedOverride !== null) cmd.speed_override = speedOverride;
    onSend(cmd);
  };

  return (
    <div className="stack">
      <div className="preset-grid">
        {presets.map((name) => (
          <button
            key={name}
            className={`preset-card ${selected === name ? 'active' : ''}`}
            style={{ 
              backgroundImage: PRESET_GRADIENTS[name] || 'var(--card-bg)',
              border: selected === name ? '2px solid var(--accent)' : '2px solid transparent'
            }}
            onClick={() => setSelected(name)}
          >
            {name.replace(/_/g, ' ')}
          </button>
        ))}
      </div>

      {selected && (
        <div className="card" style={{ marginTop: 'var(--sp-4)' }}>
          <div className="card-header">
            <span>Controls: {selected.replace(/_/g, ' ')}</span>
          </div>
          
          <div className="slider-group" style={{ marginTop: 'var(--sp-2)' }}>
            <div className="slider-header">
              <span>Text Speed</span>
              <span>{speedOverride === null ? 'Recommended' : speedOverride}</span>
            </div>
            <div style={{ display: 'flex', gap: 'var(--sp-4)', alignItems: 'center' }}>
              <input
                type="range"
                min={1}
                max={255}
                value={speedOverride === null ? 25 : speedOverride}
                onChange={(e) => setSpeedOverride(Number(e.target.value))}
                className="slider"
                style={{ flex: 1 }}
              />
              <button 
                className="btn btn-ghost" 
                style={{ padding: 'var(--sp-1) var(--sp-2)', fontSize: '10px' }}
                onClick={() => setSpeedOverride(null)}
              >RESET</button>
            </div>
          </div>

          <button
            className="btn btn-primary"
            style={{ width: '100%', marginTop: 'var(--sp-4)', padding: 'var(--sp-4)' }}
            onClick={() => handlePush(selected)}
          >
            Push Preset to Matrix
          </button>
        </div>
      )}
    </div>
  );
}
