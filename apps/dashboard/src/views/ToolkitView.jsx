import { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';

const SWATCHES = [
  '#ef4444', '#f97316', '#facc15', '#22c55e', '#06b6d4',
  '#3b82f6', '#8b5cf6', '#ec4899', '#ffffff', '#000000',
];

function hexToRgb(hex) {
  const h = hex.replace('#', '');
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  };
}

export default function ToolkitView({ group, color, onColorChange, brightness, onBrightnessChange, onCommandSent }) {
  const [effects, setEffects] = useState([]);
  const [emoji, setEmoji] = useState({});
  const [devices, setDevices] = useState([]);
  const [selectedEffect, setSelectedEffect] = useState('');
  const [speed, setSpeed] = useState(225);
  const [intensity, setIntensity] = useState(128);
  const [hexInput, setHexInput] = useState(color || '#ff7a00');
  const [sending, setSending] = useState(false);

  // Sync hexInput when color prop changes
  useEffect(() => {
    if (color) setHexInput(color);
  }, [color]);

  // Load data on mount + every 10s
  useEffect(() => {
    const load = () => {
      api.listEffects()
        .then((d) => {
          setEffects(d.effects);
          setSelectedEffect((prev) => prev || d.effects[0] || '');
        })
        .catch(() => {});
      api.listEmoji().then((d) => setEmoji(d.emoji || {})).catch(() => {});
      api.listDevices().then((d) => setDevices(d.devices || [])).catch(() => {});
    };
    load();
    const id = setInterval(load, 10_000);
    return () => clearInterval(id);
  }, []);

  const send = useCallback(async (command) => {
    setSending(true);
    try {
      await api.broadcastCommand(group, command);
      if (onCommandSent) onCommandSent(command);
    } catch {
      // silently handle
    } finally {
      setSending(false);
    }
  }, [group, onCommandSent]);

  const handleSwatchClick = (hex) => {
    onColorChange(hex);
    send({ kind: 'color', color: hexToRgb(hex), brightness });
  };

  const handleHexSet = () => {
    const normalized = hexInput.startsWith('#') ? hexInput : `#${hexInput}`;
    if (/^#[\da-f]{6}$/i.test(normalized)) {
      onColorChange(normalized);
      send({ kind: 'color', color: hexToRgb(normalized), brightness });
    }
  };

  const handleFireEffect = () => {
    send({
      kind: 'effect',
      name: selectedEffect,
      color: hexToRgb(color || '#ff7a00'),
      speed,
      intensity,
      brightness,
    });
  };

  const handleRescan = async () => {
    setSending(true);
    try {
      await api.rescan();
      const d = await api.listDevices();
      setDevices(d.devices || []);
    } catch {
      // silently handle
    } finally {
      setSending(false);
    }
  };

  const emojiKeys = Object.keys(emoji);

  return (
    <div className="toolkit-view">
      {/* Colors */}
      <section>
        <div className="card-header">Colors</div>
        <div className="toolkit-color-grid">
          {SWATCHES.map((hex) => (
            <button
              key={hex}
              type="button"
              className={`toolkit-swatch${color === hex ? ' active' : ''}`}
              style={{ background: hex }}
              onClick={() => handleSwatchClick(hex)}
              disabled={sending}
              aria-label={`Color ${hex}`}
            />
          ))}
        </div>
        <div className="inline-row" style={{ marginTop: 'var(--sp-2)' }}>
          <input
            className="input"
            value={hexInput}
            onChange={(e) => setHexInput(e.target.value)}
            placeholder="#ff7a00"
            style={{ flex: 1 }}
          />
          <button className="btn btn-primary" onClick={handleHexSet} disabled={sending}>SET</button>
        </div>
      </section>

      {/* Effects */}
      <section>
        <div className="card-header">Effects</div>
        <select
          className="toolkit-select"
          value={selectedEffect}
          onChange={(e) => setSelectedEffect(e.target.value)}
        >
          {effects.map((e) => (
            <option key={e} value={e}>{e}</option>
          ))}
        </select>
        <div className="toolkit-slider-row">
          <span className="toolkit-slider-label">Speed</span>
          <input
            type="range"
            min={0}
            max={255}
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
            className="slider"
            style={{ flex: 1 }}
          />
          <span className="toolkit-slider-value">{speed}</span>
        </div>
        <div className="toolkit-slider-row">
          <span className="toolkit-slider-label">Intensity</span>
          <input
            type="range"
            min={0}
            max={255}
            value={intensity}
            onChange={(e) => setIntensity(Number(e.target.value))}
            className="slider"
            style={{ flex: 1 }}
          />
          <span className="toolkit-slider-value">{intensity}</span>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleFireEffect}
          disabled={sending}
          style={{ width: '100%', justifyContent: 'center', marginTop: 'var(--sp-2)' }}
        >
          Fire Effect
        </button>
      </section>

      {/* Emoji */}
      {emojiKeys.length > 0 && (
        <section>
          <div className="card-header">Emoji</div>
          <div className="toolkit-emoji-grid">
            {emojiKeys.map((key) => (
              <button
                key={key}
                type="button"
                className="toolkit-emoji-btn"
                onClick={() => send(emoji[key].command)}
                disabled={sending}
                title={emoji[key].label}
              >
                {key}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* Devices */}
      <section>
        <div className="card-header">Devices</div>
        <div className="toolkit-device-list">
          {devices.map((d) => (
            <div key={d.mac} className="toolkit-device-row">
              <div>
                <div className="toolkit-device-name">{d.name || d.mac}</div>
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                  {d.led_count ?? '?'} LEDs
                </div>
              </div>
              <span className={`toolkit-device-status${d.on ? '' : ' off'}`}>
                {d.on ? 'ON' : 'OFF'}
              </span>
            </div>
          ))}
          {devices.length === 0 && (
            <div className="empty-state">No devices found</div>
          )}
        </div>
        <button
          className="btn"
          onClick={handleRescan}
          disabled={sending}
          style={{ width: '100%', justifyContent: 'center', marginTop: 'var(--sp-2)' }}
        >
          Rescan for devices
        </button>
      </section>

      {/* Brightness (using onBrightnessChange prop) */}
      {onBrightnessChange && (
        <section>
          <div className="card-header">Brightness</div>
          <div className="toolkit-slider-row">
            <span className="toolkit-slider-label">Level</span>
            <input
              type="range"
              min={0}
              max={200}
              value={brightness}
              onChange={(e) => onBrightnessChange(Number(e.target.value))}
              className="slider"
              style={{ flex: 1 }}
            />
            <span className="toolkit-slider-value">{brightness}</span>
          </div>
        </section>
      )}
    </div>
  );
}
