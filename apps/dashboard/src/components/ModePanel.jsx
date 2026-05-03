import { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';

const MODES = [
  { id: 'idle', label: 'Idle', desc: 'Manual control (default)' },
  { id: 'clock', label: 'Clock', desc: 'Show current time' },
  { id: 'schedule', label: 'Schedule', desc: 'Auto-show current/next talk' },
  { id: 'countdown_minutes', label: 'Countdown', desc: 'Count down N minutes' },
  { id: 'countdown_to', label: 'Count To', desc: 'Count down to a specific time' },
];

export default function ModePanel() {
  const [current, setCurrent] = useState(null);
  const [minutes, setMinutes] = useState(5);
  const [target, setTarget] = useState('');
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const cfg = await api.getMode();
      setCurrent(cfg);
      setError(null);
    } catch (e) { setError(e.message); }
  }, []);

  useEffect(() => {
    let mounted = true;
    const poll = async () => { if (mounted) await refresh(); };
    poll();
    const h = setInterval(poll, 5000);
    return () => { mounted = false; clearInterval(h); };
  }, [refresh]);

  const setMode = async (mode, extra = {}) => {
    try {
      const cfg = await api.setMode({ mode, ...extra });
      setCurrent(cfg);
      setError(null);
    } catch (e) { setError(e.message); }
  };

  return (
    <div className="card" style={{ marginBottom: 'var(--sp-4)' }}>
      <div className="card-header">
        <span>Matrix Mode</span>
        <span style={{ fontSize: 'var(--text-xs)', color: current?.mode === 'idle' ? 'var(--text-disabled)' : 'var(--success)' }}>
          {current?.mode || '...'}
        </span>
      </div>
      {error && <div className="banner-error" style={{ margin: 'var(--sp-2)' }}>{error}</div>}
      <div style={{ padding: 'var(--sp-3)', display: 'flex', flexWrap: 'wrap', gap: 'var(--sp-2)' }}>
        {MODES.map((m) => (
          <button
            key={m.id}
            className={current?.mode === m.id ? 'btn btn-primary' : 'btn'}
            onClick={() => {
              if (m.id === 'countdown_minutes') {
                setMode(m.id, { minutes });
              } else if (m.id === 'countdown_to') {
                if (!target) return;
                setMode(m.id, { target });
              } else {
                setMode(m.id);
              }
            }}
            title={m.desc}
          >
            {m.label}
          </button>
        ))}
      </div>
      <div style={{ padding: '0 var(--sp-3) var(--sp-3)', display: 'flex', gap: 'var(--sp-3)', flexWrap: 'wrap', alignItems: 'center' }}>
        <label className="field-label" style={{ margin: 0 }}>
          Minutes:
          <input
            type="number" min={1} max={120} value={minutes}
            className="input" style={{ width: '4rem', marginLeft: 'var(--sp-1)' }}
            onChange={(e) => setMinutes(parseInt(e.target.value, 10) || 5)}
          />
        </label>
        <label className="field-label" style={{ margin: 0 }}>
          Target time:
          <input
            type="datetime-local" value={target}
            className="input" style={{ marginLeft: 'var(--sp-1)' }}
            onChange={(e) => setTarget(e.target.value)}
          />
        </label>
      </div>
    </div>
  );
}
