import { useEffect, useState } from 'react';
import { api } from '../api.js';

function rgbFrom(col) {
  if (!col || col.length < 3) return null;
  return `rgb(${col[0]},${col[1]},${col[2]})`;
}

function hexFrom(col) {
  if (!col || col.length < 3) return '';
  const to = (n) => n.toString(16).padStart(2, '0');
  return `#${to(col[0])}${to(col[1])}${to(col[2])}`;
}

export default function LiveState({ selectedMac }) {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!selectedMac) return undefined;
    let cancelled = false;
    const poll = async () => {
      try {
        const s = await api.getState(selectedMac);
        if (!cancelled) { setState(s); setError(null); }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    };
    poll();
    const handle = setInterval(poll, 2000);
    return () => { cancelled = true; clearInterval(handle); };
  }, [selectedMac]);

  if (error) return <div className="live-empty">⚠ {error}</div>;
  if (!state) return <div className="live-empty">loading…</div>;

  const seg = state.seg?.[0] || {};
  const col = seg.col?.[0];
  const swatchColor = rgbFrom(col) || 'var(--surface-3)';
  const hex = hexFrom(col);

  return (
    <div className="live-state">
      <div
        className={state.on ? 'live-swatch on' : 'live-swatch'}
        style={{
          background: swatchColor,
          '--swatch-glow': state.on ? swatchColor : 'transparent',
        }}
      />
      <div className="live-meta">
        <div className="live-row">
          <span className="live-state-label">
            <span className={state.on ? 'live-dot on' : 'live-dot off'} />
            {state.on ? 'ON' : 'OFF'}
          </span>
          <span>bri <strong>{state.bri}</strong></span>
        </div>
        <div className="live-row">
          <span>fx {seg.fx}</span>
          {hex && <span className="live-hex">{hex}</span>}
        </div>
        <div className="live-row">
          <span className="live-pulse"><span className="live-dot" />live</span>
        </div>
      </div>
    </div>
  );
}
