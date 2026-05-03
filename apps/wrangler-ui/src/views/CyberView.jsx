import React, { useState } from 'react';

const EFFECT_MAP = {
  'Matrix Rain': 'matrix',
  'Python Pulse': 'breathe',
  'Plasma': 'plasma',
  'Rainbow': 'rainbow',
  'GLITCH': 'noise',
  'PARTY': 'rainbow',
  'SNAKE': 'chase',
  'WARP': 'meteor'
};

export default function CyberView({ onSend, selectedMac }) {
  const [fps] = useState(60.2);
  const [brightness, setBrightness] = useState(128);
  const [logs, setLogs] = useState([
    { id: 1, level: 'INFO', msg: 'Cyber Protocol Initialized', opacity: 'opacity-50' },
    { id: 2, level: 'SYSTEM', msg: 'Chaos Engine: Standby', animate: true }
  ]);
  const [text, setText] = useState('');

  const addLog = (level, msg) => {
    setLogs(prev => [...prev, { id: Date.now(), level, msg, opacity: 'opacity-100' }].slice(-5));
  };

  const handleSend = async () => {
    if (!text || !onSend) return;
    try {
      await onSend({ kind: 'text', text, speed: 200 });
      addLog('USER', `Local Send: ${text}`);
      setText('');
    } catch (e) { console.error(e); }
  };

  const handleAction = async (type, name) => {
    if (!onSend) return;
    try {
      const internalName = EFFECT_MAP[name] || name.toLowerCase();
      const cmd = type === 'effect' ? { kind: 'effect', name: internalName } : { kind: 'preset', name };
      await onSend(cmd);
      addLog('ACTION', `${name} Activated`);
    } catch (e) { console.error(e); }
  };

  const handleBrightness = (val) => {
    setBrightness(val);
    if (onSend) onSend({ kind: 'brightness', brightness: parseInt(val) });
  };

  return (
    <div className="bg-slate-950 text-slate-100 font-sans min-h-screen">
      <header className="border-b border-slate-800 p-4 flex justify-between items-center bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-yellow-500 bg-clip-text text-transparent">
            PYTHONEER WRANGLER
          </h1>
          <p className="text-xs text-slate-500 uppercase tracking-widest">Hardware Control Dashboard</p>
        </div>
        <div className="flex gap-4 items-center">
          <div className="text-right">
            <span className="block text-xs text-slate-500">FPS</span>
            <span className="font-mono text-green-400">{fps.toFixed(1)}</span>
          </div>
          <button 
            onClick={() => window.confirm('EMERGENCY OFF?') && onSend?.({kind:'power', on:false})}
            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-full font-bold text-sm transition-all transform active:scale-95"
          >
            OFF
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto p-6 space-y-8">
        {!selectedMac && (
          <div className="bg-red-900/20 border border-red-500/50 text-red-200 p-4 rounded-xl text-center animate-pulse">
            ⚠️ No Device Selected. Use the sidebar to pick a device.
          </div>
        )}
        
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
            <h2 className="text-sm font-semibold text-slate-400 mb-4 uppercase flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
              Brightness
            </h2>
            <input 
              type="range" min="0" max="255" value={brightness}
              onChange={(e) => handleBrightness(e.target.value)}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
          </div>

          <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
            <h2 className="text-sm font-semibold text-slate-400 mb-4 uppercase">Core Patterns</h2>
            <div className="grid grid-cols-2 gap-2">
              {['Matrix Rain', 'Python Pulse', 'Plasma', 'Rainbow'].map(p => (
                <button 
                  key={p} onClick={() => handleAction('effect', p)}
                  className="bg-slate-800 hover:bg-blue-900/40 border border-slate-700 p-2 rounded-xl text-sm"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* CHAOS CONTROLS */}
        <section className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
          <h2 className="text-sm font-semibold text-purple-400 mb-4 uppercase flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-500 animate-ping"></span>
            Chaos Protocol
          </h2>
          <div className="grid grid-cols-4 gap-3">
            {[
              { id: 'glitch', label: 'GLITCH', icon: '⚡' },
              { id: 'party', label: 'PARTY', icon: '🎉' },
              { id: 'snake', label: 'SNAKE', icon: '🐍' },
              { id: 'warp', label: 'WARP', icon: '✨' }
            ].map(item => (
              <button 
                key={item.id}
                onClick={() => handleAction('effect', item.label)}
                className="bg-slate-950/50 hover:bg-slate-800 border border-slate-800 p-3 rounded-xl transition-all"
              >
                <span className="block text-xl mb-1">{item.icon}</span>
                <span className="font-bold text-[10px]">{item.label}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
          <h2 className="text-sm font-semibold text-slate-400 mb-4 uppercase tracking-tighter">Live Ticker</h2>
          <div className="flex gap-2">
            <input 
              type="text" value={text} onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Local message..." 
              className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none"
            />
            <button onClick={handleSend} className="bg-blue-600 px-6 py-3 rounded-xl font-bold transition-all">SEND</button>
          </div>
        </section>

        <section className="bg-black rounded-xl p-4 border border-slate-800 font-mono text-[10px] text-blue-400 overflow-hidden h-32 relative">
          <div className="absolute top-2 right-4 text-[8px] uppercase tracking-widest text-slate-700">Pi Uplink</div>
          {logs.map(log => (
            <div key={log.id} className={`${log.opacity || ''} mb-1`}>
              <span className="text-slate-600">[{new Date(log.id).toLocaleTimeString([], {hour12:false})}]</span> [{log.level}] {log.msg}
            </div>
          ))}
          <div className="text-white">&gt; _</div>
        </section>
      </main>
    </div>
  );
}
