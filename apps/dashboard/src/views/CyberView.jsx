import React, { useState } from 'react';
import { api } from '../api.js';

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

export default function CyberView() {
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
    if (!text) return;
    try {
      if (api.broadcastCommand) {
        await api.broadcastCommand('all', { kind: 'text', text, speed: 200 });
      } else {
        const { devices } = await api.listDevices();
        if (devices.length) await api.sendCommand(devices[0].mac, { kind: 'text', text, speed: 200 });
      }
      addLog('USER', `Broadcast: ${text}`);
      setText('');
    } catch (e) { console.error(e); }
  };

  const handleAction = async (type, name, color = null) => {
    try {
      const internalName = EFFECT_MAP[name] || name.toLowerCase();
      const cmd = type === 'effect' ? { kind: 'effect', name: internalName } : { kind: 'preset', name };
      if (color) cmd.color = color;
      
      if (api.broadcastCommand) {
        await api.broadcastCommand('all', cmd);
      } else {
        const { devices } = await api.listDevices();
        if (devices.length) await api.sendCommand(devices[0].mac, cmd);
      }
      addLog('ACTION', `${name} Activated`);
    } catch (e) { console.error(e); }
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
            onClick={() => window.confirm('EMERGENCY OFF?') && api.modEmergencyOff?.()}
            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-full font-bold text-sm transition-all transform active:scale-95"
          >
            EMERGENCY OFF
          </button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto p-6 space-y-8">
        
        <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
            <h2 className="text-sm font-semibold text-slate-400 mb-4 uppercase tracking-tighter flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></span>
              Master Brightness
            </h2>
            <input 
              type="range" min="0" max="255" value={brightness}
              onChange={(e) => {
                setBrightness(e.target.value);
                api.broadcastCommand?.('all', { kind: 'brightness', brightness: parseInt(e.target.value) });
              }}
              className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <div className="flex justify-between text-xs mt-2 text-slate-500 font-mono">
              <span>0%</span><span>50%</span><span>100%</span>
            </div>
          </div>

          <div className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
            <h2 className="text-sm font-semibold text-slate-400 mb-4 uppercase tracking-tighter flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-yellow-500"></span>
              Core Patterns
            </h2>
            <div className="grid grid-cols-2 gap-2">
              {['Matrix Rain', 'Python Pulse', 'Plasma', 'Rainbow'].map(p => (
                <button 
                  key={p} onClick={() => handleAction('effect', p)}
                  className="bg-slate-800 hover:bg-blue-900/40 border border-slate-700 p-3 rounded-xl transition-all hover:border-blue-500/50 active:scale-95 text-sm font-medium"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* CHAOS CONTROLS */}
        <section className="bg-slate-900 p-6 rounded-2xl border border-slate-800 relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-r from-purple-500/5 to-pink-500/5 opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <h2 className="text-sm font-semibold text-purple-400 mb-4 uppercase tracking-tighter flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-500 animate-ping"></span>
            Chaos Protocol
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { id: 'glitch', label: 'GLITCH', icon: '⚡', color: 'text-cyan-400' },
              { id: 'party', label: 'PARTY', icon: '🎉', color: 'text-pink-400' },
              { id: 'snake', label: 'SNAKE', icon: '🐍', color: 'text-green-400' },
              { id: 'warp', label: 'WARP', icon: '✨', color: 'text-white' }
            ].map(item => (
              <button 
                key={item.id}
                onClick={() => handleAction('effect', item.label)}
                className="bg-slate-950/50 hover:bg-slate-800 border border-slate-800 p-4 rounded-xl transition-all hover:border-purple-500/50 group/btn"
              >
                <span className="block text-xl mb-1 group-hover/btn:scale-125 transition-transform">{item.icon}</span>
                <span className={`font-bold text-xs ${item.color}`}>{item.label}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="bg-slate-900 p-6 rounded-2xl border border-slate-800">
          <h2 className="text-sm font-semibold text-slate-400 mb-4 uppercase">Live Text Ticker</h2>
          <div className="flex gap-2">
            <input 
              type="text" value={text} onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Type a message for the panel..." 
              className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button onClick={handleSend} className="bg-blue-600 hover:bg-blue-500 px-6 py-3 rounded-xl font-bold transition-all shadow-lg shadow-blue-900/20">SEND</button>
          </div>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button 
            onClick={() => handleAction('preset', 'PIZZA')}
            className="bg-orange-600/20 border border-orange-500/50 text-orange-400 p-4 rounded-2xl hover:bg-orange-600/30 transition-all group"
          >
            <span className="block text-2xl mb-1 group-hover:scale-110 transition-transform">🍕</span>
            <span className="font-bold">PIZZA ALERT</span>
          </button>
          <button 
            onClick={() => handleAction('preset', 'RAFFLE')}
            className="bg-purple-600/20 border border-purple-500/50 text-purple-400 p-4 rounded-2xl hover:bg-purple-600/30 transition-all group"
          >
            <span className="block text-2xl mb-1 group-hover:rotate-12 transition-transform">🎟️</span>
            <span className="font-bold">RAFFLE MODE</span>
          </button>
          <button 
            onClick={() => handleAction('preset', 'TIMER')}
            className="bg-green-600/20 border border-green-500/50 text-green-400 p-4 rounded-2xl hover:bg-green-600/30 transition-all group"
          >
            <span className="block text-2xl mb-1 group-hover:animate-pulse">⏳</span>
            <span className="font-bold">SPEAKER TIMER</span>
          </button>
        </section>

        <section className="bg-black rounded-xl p-4 border border-slate-800 font-mono text-[10px] text-blue-400 overflow-hidden h-32 relative">
          <div className="absolute top-2 right-4 text-[8px] uppercase tracking-widest text-slate-700 animate-pulse">Live Uplink</div>
          {logs.map(log => (
            <div key={log.id} className={`${log.opacity || ''} ${log.animate ? 'animate-pulse' : ''} mb-1`}>
              <span className="text-slate-600">[{new Date(log.id).toLocaleTimeString([], {hour12:false})}]</span> <span className={log.level === 'ACTION' ? 'text-purple-400' : ''}>[{log.level}]</span> {log.msg}
            </div>
          ))}
          <div className="text-white">&gt; _</div>
        </section>
      </main>
    </div>
  );
}
