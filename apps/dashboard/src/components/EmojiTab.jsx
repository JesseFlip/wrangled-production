import { useEffect, useState } from 'react';
import { api } from '../api.js';

export default function EmojiTab({ onSend }) {
  const [items, setItems] = useState({});
  useEffect(() => {
    api.listEmoji().then((d) => setItems(d.emoji)).catch(() => {});
  }, []);

  const glyphs = Object.keys(items);

  return (
    <div className="emoji-grid">
      {glyphs.map((g) => (
        <button
          key={g}
          className="emoji-chip"
          onClick={() => onSend(items[g].command)}
          title={items[g].label}
        >
          <span className="emoji-glyph">{g}</span>
          <span className="emoji-label">{items[g].label}</span>
        </button>
      ))}
    </div>
  );
}
