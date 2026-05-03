import { useState } from 'react';
import { api } from '../api.js';

const SYSTEM_SOURCES = new Set(['system', 'admin', 'api-user']);

function shortTime(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '';
  }
}

export default function StreamCard({ event, onBanned }) {
  const [banning, setBanning] = useState(false);

  const isFlagged =
    event.flag === 'content_blocked' ||
    event.flag === 'rate_limited' ||
    event.flag === true;
  const isBlocked = event.result === 'blocked';
  const showBan = !SYSTEM_SOURCES.has(event.source) && event.who;

  const handleBan = async () => {
    const reason = window.prompt(`Ban "${event.who}"? Enter reason:`);
    if (reason === null) return;
    setBanning(true);
    try {
      await api.modBan(event.who, event.who, reason);
      onBanned?.(event.who);
    } catch {
      // silently fail — mod view shows ban state
    } finally {
      setBanning(false);
    }
  };

  let cardClass = 'stream-card';
  if (isFlagged) cardClass += ' flagged';
  if (isBlocked) cardClass += ' blocked';

  return (
    <div className={cardClass}>
      <div className="stream-card-body">
        <div className="stream-card-header">
          <span className={isFlagged ? 'stream-card-who flagged' : 'stream-card-who'}>
            {event.who || 'unknown'}
          </span>
          {isFlagged && <span className="stream-flag-indicator">flagged</span>}
          <span className="stream-card-time">{shortTime(event.timestamp)}</span>
        </div>
        {event.content && (
          <div className={isBlocked ? 'stream-card-content blurred' : 'stream-card-content'}>
            {event.content}
          </div>
        )}
        <div className="stream-card-meta">
          {event.command_kind}{event.target ? ` \u2192 ${event.target}` : ''}
          {event.result && event.result !== 'ok' && ` \u00b7 ${event.result}`}
          {event.flag_reason && ` \u00b7 ${event.flag_reason}`}
        </div>
      </div>
      {showBan && (
        <button
          className={isFlagged ? 'stream-ban-btn prominent' : 'stream-ban-btn'}
          disabled={banning}
          onClick={handleBan}
        >
          {isFlagged ? 'BAN' : 'ban'}
        </button>
      )}
    </div>
  );
}
