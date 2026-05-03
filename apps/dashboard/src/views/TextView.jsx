import { useCallback, useEffect, useState } from 'react';
import { api } from '../api.js';

function hexToRgb(hex) {
  const result = /^#([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  if (!result) return { r: 255, g: 128, b: 0 };
  return {
    r: parseInt(result[1], 16),
    g: parseInt(result[2], 16),
    b: parseInt(result[3], 16),
  };
}

export default function TextView({ group, color, brightness, speed, onCommandSent }) {
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [quickTexts, setQuickTexts] = useState([]);

  useEffect(() => {
    api.listQuickTexts().then((r) => setQuickTexts(r.texts || [])).catch(() => {});
  }, []);

  const sendMessage = useCallback(async (msg) => {
    const trimmed = msg.trim();
    if (!trimmed) return;
    setSending(true);
    try {
      const cmd = {
        kind: 'text',
        text: trimmed,
        color: hexToRgb(color),
        speed,
        brightness,
      };
      await api.broadcastCommand(group, cmd);
      if (onCommandSent) onCommandSent(cmd);
    } catch {
      /* swallow */
    } finally {
      setSending(false);
    }
  }, [group, color, brightness, speed, onCommandSent]);

  const addQuickText = async () => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const r = await api.addQuickText(trimmed).catch(() => null);
    if (r) setQuickTexts(r.texts || []);
    setText('');
  };

  const removeQuickText = async (msg) => {
    const r = await api.removeQuickText(msg).catch(() => null);
    if (r) setQuickTexts(r.texts || []);
  };

  return (
    <div className="command-view">
      <section className="command-section">
        <div className="section-label">Send Text</div>
        <div className="quick-text-row">
          <input
            className="quick-text-input"
            type="text"
            placeholder="Type a message..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { sendMessage(text); setText(''); } }}
          />
          <button
            className="btn-accent"
            disabled={sending || !text.trim()}
            onClick={() => { sendMessage(text); setText(''); }}
          >
            SEND
          </button>
        </div>
        {text.trim() && (
          <button className="canned-chip" style={{ marginTop: 'var(--sp-1)' }} onClick={addQuickText}>
            + Save as quick text
          </button>
        )}
      </section>

      <section className="command-section">
        <div className="section-label">Quick Messages</div>
        <div className="canned-chips">
          {quickTexts.map((msg) => (
            <span key={msg} className="canned-chip-wrap">
              <button
                className="canned-chip"
                disabled={sending}
                onClick={() => sendMessage(msg)}
              >
                {msg}
              </button>
              <button
                className="canned-chip-remove"
                onClick={() => removeQuickText(msg)}
                title="Remove"
              >
                ×
              </button>
            </span>
          ))}
          {quickTexts.length === 0 && (
            <span style={{ color: 'var(--text-disabled)', fontSize: 'var(--text-xs)' }}>
              Type a message above and tap &quot;Save as quick text&quot;
            </span>
          )}
        </div>
      </section>
    </div>
  );
}
