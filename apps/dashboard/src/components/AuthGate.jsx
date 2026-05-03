import { useEffect, useState } from 'react';
import { api } from '../api.js';

const TOKEN_KEY = 'wrangled.token';

export default function AuthGate({ children }) {
  const [state, setState] = useState('checking'); // checking | needs_auth | ok
  const [draft, setDraft] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api.listDevices().then(() => {
      if (!cancelled) setState('ok');
    }).catch((e) => {
      if (cancelled) return;
      if (e.message === 'AUTH_REQUIRED') {
        setState('needs_auth');
      } else {
        // Network error or server down — try without auth (dev mode)
        setState('ok');
      }
    });
    return () => { cancelled = true; };
  }, []);

  const submit = async () => {
    if (!draft.trim()) return;
    localStorage.setItem(TOKEN_KEY, draft.trim());
    setError(null);
    try {
      await api.listDevices();
      setState('ok');
    } catch (e) {
      if (e.message === 'AUTH_REQUIRED') {
        setError('Invalid token');
        localStorage.removeItem(TOKEN_KEY);
      }
    }
  };

  if (state === 'checking') {
    return <div className="empty-state">Connecting...</div>;
  }

  if (state === 'needs_auth') {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <div className="card" style={{ maxWidth: '24rem', width: '100%' }}>
          <div className="card-header"><span>Authentication Required</span></div>
          <div className="stack" style={{ padding: 'var(--sp-4)' }}>
            <label className="field-label">Enter auth token</label>
            <input
              className="input"
              type="password"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') submit(); }}
              placeholder="devtoken"
              autoFocus
            />
            {error && <div style={{ color: 'var(--danger)', fontSize: 'var(--text-sm)' }}>{error}</div>}
            <button className="btn btn-primary" onClick={submit}>Connect</button>
          </div>
        </div>
      </div>
    );
  }

  return children;
}
