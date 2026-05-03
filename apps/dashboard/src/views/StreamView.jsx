import { useEffect, useState } from 'react';
import { api, subscribeStream } from '../api.js';
import StreamCard from '../components/StreamCard.jsx';

const MAX_EVENTS = 50;

export default function StreamView({ group }) {
  const [events, setEvents] = useState([]);

  // Backfill history on mount, then subscribe to live events. State stores
  // newest-first so the UI can render in declared order. Events that arrive
  // during the history fetch are buffered and merged once it resolves.
  useEffect(() => {
    let cancelled = false;
    let history = null;
    const liveBuffer = [];

    const flushIfReady = () => {
      if (cancelled || history === null) return;
      // history is oldest-first from the server; reverse so newest is at [0].
      // liveBuffer is arrival order; reverse so the most recent event is at [0].
      const merged = [...liveBuffer.slice().reverse(), ...history.slice().reverse()];
      setEvents(merged.slice(0, MAX_EVENTS));
    };

    api.recentCommands(MAX_EVENTS)
      .then((res) => {
        if (cancelled) return;
        history = res.events || [];
        flushIfReady();
      })
      .catch(() => {
        if (cancelled) return;
        history = [];
        flushIfReady();
      });

    const source = subscribeStream((evt) => {
      if (history === null) {
        liveBuffer.push(evt);
        return;
      }
      setEvents((prev) => [evt, ...prev].slice(0, MAX_EVENTS));
    });

    return () => {
      cancelled = true;
      source.close();
    };
  }, []);

  const visible = group === 'all'
    ? events
    : events.filter((e) => e.target === group);

  return (
    <div className="stream-view">
      {visible.length === 0 && (
        <div className="stream-empty">Waiting for commands...</div>
      )}
      {visible.map((evt, i) => (
        <StreamCard key={`${evt.timestamp}-${i}`} event={evt} />
      ))}
    </div>
  );
}
