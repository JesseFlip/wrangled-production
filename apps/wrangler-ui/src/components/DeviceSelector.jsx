import { useState } from 'react';
import { api } from '../api.js';

export default function DeviceSelector({ devices, selectedMac, onSelect, onRescan, onRenamed }) {
  const [renaming, setRenaming] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const current = devices.find((d) => d.mac === selectedMac);

  const commitRename = async () => {
    if (!current || !draft.trim()) { setRenaming(false); return; }
    setBusy(true);
    try {
      await api.rename(current.mac, draft.trim());
      onRenamed?.();
    } finally {
      setBusy(false);
      setRenaming(false);
    }
  };

  const rescan = async () => {
    setBusy(true);
    try { await onRescan?.(); } finally { setBusy(false); }
  };

  return (
    <header className="app-header">
      <h1 className="app-title">
        Wrang<span className="app-title-accent">LED</span>
      </h1>
      <select
        className="select"
        value={selectedMac || ''}
        onChange={(e) => onSelect(e.target.value)}
      >
        {devices.map((d) => (<option key={d.mac} value={d.mac}>{d.name}</option>))}
      </select>
      {current && !renaming && (
        <>
          <span className="device-info">
            {current.ip} · {current.matrix ? `${current.matrix.width}x${current.matrix.height}` : `${current.led_count} LEDs`} · v{current.version}
          </span>
          <button className="btn btn-ghost" onClick={() => { setDraft(current.name); setRenaming(true); }}>✏️ rename</button>
        </>
      )}
      {current && renaming && (
        <>
          <input
            className="input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') setRenaming(false); }}
            autoFocus
          />
          <button className="btn btn-primary" disabled={busy} onClick={commitRename}>save</button>
          <button className="btn btn-ghost" disabled={busy} onClick={() => setRenaming(false)}>cancel</button>
        </>
      )}
      <button className="btn btn-rescan" disabled={busy} onClick={rescan}>
        {busy ? 'Scanning…' : 'Rescan 🔄'}
      </button>
    </header>
  );
}
