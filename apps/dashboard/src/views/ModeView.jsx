import { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';

const COUNTDOWN_PRESETS = [
  { label: '1 min', minutes: 1 },
  { label: '5 min', minutes: 5 },
  { label: '10 min', minutes: 10 },
  { label: '15 min', minutes: 15 },
];

export default function ModeView() {
  const [mode, setMode] = useState(null);
  const [sending, setSending] = useState(false);
  const [customMinutes, setCustomMinutes] = useState('');

  useEffect(() => {
    const load = () => api.getMode().then(setMode).catch(() => {});
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  const changeMode = useCallback(async (name, opts) => {
    setSending(true);
    try {
      if (name === 'idle') {
        await api.goIdle();
      } else {
        await api.setMode({ mode: name, ...opts });
      }
      setMode(await api.getMode());
    } catch {
      /* swallow */
    } finally {
      setSending(false);
    }
  }, []);

  const startCountdown = useCallback((minutes) => {
    if (minutes > 0) changeMode('countdown_minutes', { minutes });
  }, [changeMode]);

  const activeMode = mode?.mode ?? null;
  const isCountdown = activeMode?.startsWith('countdown');

  return (
    <div className="command-view">
      <section className="command-section">
        <div className="section-label">Auto Mode</div>
        <div className="mode-pills">
          {['idle', 'clock', 'schedule'].map((name) => (
            <button
              key={name}
              className={`mode-pill${activeMode === name ? ' active' : ''}`}
              disabled={sending}
              onClick={() => changeMode(name)}
            >
              {name}
            </button>
          ))}
        </div>
      </section>

      <section className="command-section">
        <div className="section-label">Countdown</div>
        <div className="countdown-presets">
          {COUNTDOWN_PRESETS.map(({ label, minutes }) => (
            <button
              key={minutes}
              className="countdown-btn"
              disabled={sending}
              onClick={() => startCountdown(minutes)}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="quick-text-row" style={{ marginTop: 'var(--sp-2)' }}>
          <input
            className="quick-text-input"
            type="number"
            min={1}
            max={999}
            placeholder="Custom minutes..."
            value={customMinutes}
            onChange={(e) => setCustomMinutes(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                startCountdown(Number(customMinutes));
                setCustomMinutes('');
              }
            }}
          />
          <button
            className="btn-accent"
            disabled={sending || !customMinutes || Number(customMinutes) <= 0}
            onClick={() => { startCountdown(Number(customMinutes)); setCustomMinutes(''); }}
          >
            GO
          </button>
        </div>
      </section>

      {isCountdown && (
        <section className="command-section">
          <div className="section-label">Active Countdown</div>
          <div className="mode-status-card">
            <span>Counting down...</span>
            <button
              className="mode-pill active"
              onClick={() => changeMode('idle')}
              disabled={sending}
            >
              Stop
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
