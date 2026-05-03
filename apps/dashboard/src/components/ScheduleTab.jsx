import { useEffect, useState, useCallback } from 'react';
import { api } from '../api.js';

export default function ScheduleTab({ onSend }) {
  const [schedule, setSchedule] = useState(null);
  const [current, setCurrent] = useState(null);
  const [next, setNext] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [all, curr, nxt] = await Promise.all([
        api.listSchedule(),
        api.getCurrentSession(),
        api.getNextSession()
      ]);
      setSchedule(all);
      setCurrent(curr.session);
      setNext(nxt);
    } catch (e) {
      console.error("Failed to fetch schedule", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 60000); // refresh every minute
    return () => clearInterval(timer);
  }, [refresh]);

  const pushTalk = (talk) => {
    // Combine title and speaker (if present) into a single scrolling string
    const text = talk.speaker
      ? `${talk.title} - ${talk.speaker}`
      : talk.title;
    onSend({
      kind: 'text',
      text,
      color: { r: 255, g: 255, b: 255 },
      speed: 225
    });
  };

  if (loading) return <div className="live-empty">Loading schedule...</div>;
  if (!schedule) return <div className="live-empty">No schedule data available.</div>;

  return (
    <div className="stack">
      {current && (
        <div className="card" style={{ background: 'var(--accent-muted)', border: '1px solid var(--accent)' }}>
          <div className="card-header"><span style={{ color: 'var(--accent)' }}>Happening Now</span></div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 'var(--text-lg)', fontWeight: 'var(--weight-bold)' }}>{current.title}</div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--accent)' }}>{current.speaker}</div>
            </div>
            <button className="btn btn-primary" onClick={() => pushTalk(current)}>🔥 Push</button>
          </div>
        </div>
      )}

      {next?.session && (
        <div className="card">
          <div className="card-header"><span>Upcoming at {next.next_time}</span></div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ fontSize: 'var(--text-base)', fontWeight: 'var(--weight-medium)' }}>{next.session.title}</div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>{next.session.speaker}</div>
            </div>
            <button className="btn btn-ghost" onClick={() => pushTalk(next.session)}>Push</button>
          </div>
        </div>
      )}

      <div className="card-header" style={{ marginTop: 'var(--sp-4)', padding: 0 }}><span>Full Schedule</span></div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-6)' }}>
        {Object.entries(schedule).map(([date, times]) => (
          <div key={date}>
            <div style={{ 
              fontSize: 'var(--text-xs)', 
              textTransform: 'uppercase', 
              color: 'var(--brass)', 
              borderBottom: '1px solid var(--border-subtle)',
              marginBottom: 'var(--sp-3)',
              paddingBottom: 'var(--sp-1)'
            }}>
              {new Date(date).toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-4)' }}>
              {Object.entries(times).map(([time, talk]) => (
                <div key={time} style={{ display: 'flex', gap: 'var(--sp-4)' }}>
                  <div style={{ 
                    fontFamily: 'var(--font-mono)', 
                    fontSize: 'var(--text-sm)', 
                    color: 'var(--text-secondary)',
                    width: '3.5rem',
                    flexShrink: 0
                  }}>{time}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                      <div style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-medium)' }}>{talk.title}</div>
                      <button 
                        className="btn btn-ghost" 
                        style={{ padding: 'var(--sp-1) var(--sp-2)', fontSize: '10px' }}
                        onClick={() => pushTalk(talk)}
                      >PUSH</button>
                    </div>
                    {talk.speaker && <div style={{ fontSize: 'var(--text-xs)', color: 'var(--accent)' }}>{talk.speaker}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
