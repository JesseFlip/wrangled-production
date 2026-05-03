import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api.js';
import AuthGate from './components/AuthGate.jsx';
import GlobalBar from './components/GlobalBar.jsx';
import TabBar from './components/TabBar.jsx';
import CommandView from './views/CommandView.jsx';
import ModeView from './views/ModeView.jsx';
import StoryView from './views/StoryView.jsx';
import CyberView from './views/CyberView.jsx';
import StreamView from './views/StreamView.jsx';
import TextView from './views/TextView.jsx';
import ToolkitView from './views/ToolkitView.jsx';

function useHash() {
  const [hash, setHash] = useState(location.hash);
  useEffect(() => {
    const onHash = () => setHash(location.hash);
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  return hash;
}

export default function App() {
  const hash = useHash();
  const isAbout = hash === '#/about';

  const [tab, setTab] = useState('cyber'); // Default to Cyber 2.0 for the conference
  const [group, setGroup] = useState('all');
  const [groups, setGroups] = useState(['all']);
  const [brightness, setBrightness] = useState(128);
  const [speed, setSpeed] = useState(225);
  const [color, setColor] = useState('#3b82f6');
  const [deviceCount, setDeviceCount] = useState(0);
  const [discordActive, setDiscordActive] = useState(false);
  const lastCommandRef = useRef(null);

  // Child views call this after sending a text or effect command
  const trackCommand = useCallback((cmd) => {
    if (cmd.kind === 'text' || cmd.kind === 'effect') {
      lastCommandRef.current = cmd;
    }
  }, []);

  // Poll groups, devices, and health every 10s
  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const [devicesRes, healthRes, dgRes] = await Promise.allSettled([
          api.listDevices(),
          fetch('/healthz').then((r) => r.json()),
          api.listDeviceGroups(),
        ]);

        if (cancelled) return;

        if (devicesRes.status === 'fulfilled') {
          const devices = devicesRes.value?.devices ?? [];
          setDeviceCount(devices.length);

          // Derive groups from persisted device group tags
          const dgs = dgRes.status === 'fulfilled' ? (dgRes.value?.groups ?? []) : [];
          const tagSet = new Set(['all']);
          for (const dg of dgs) {
            if (dg.group) tagSet.add(dg.group);
          }
          setGroups([...tagSet]);
        }

        if (healthRes.status === 'fulfilled' && healthRes.value) {
          setDiscordActive(Boolean(healthRes.value.discord));
        }
      } catch {
        // ignore poll errors
      }
    }

    poll();
    const id = setInterval(poll, 10_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const brightnessTimer = useRef(null);
  const handleBrightnessChange = useCallback(
    (val) => {
      setBrightness(val);
      clearTimeout(brightnessTimer.current);
      brightnessTimer.current = setTimeout(() => {
        api.broadcastCommand(group, { kind: 'brightness', brightness: val }).catch(() => {});
      }, 500);
    },
    [group],
  );

  const handleKill = useCallback(() => {
    if (window.confirm('Emergency OFF — kill all lights?')) {
      api.modEmergencyOff().catch(() => {});
    }
  }, []);

  // About / Story view — separate layout
  if (isAbout) {
    return (
      <AuthGate>
        <div className="app-shell">
          <nav className="app-header">
            <a href="#/" className="nav-link">
              &larr; Back
            </a>
          </nav>
          <StoryView />
        </div>
      </AuthGate>
    );
  }

  return (
    <AuthGate>
      <div className="mobile-shell">
        <GlobalBar
          group={group}
          onGroupChange={setGroup}
          groups={groups}
          brightness={brightness}
          onBrightnessChange={handleBrightnessChange}
          speed={speed}
          onSpeedChange={setSpeed}
          color={color}
          onColorChange={(hex) => {
            setColor(hex);
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            const rgb = { r, g, b };
            api.getMode().then((m) => {
              if (m?.mode && m.mode !== 'idle') {
                api.updateModeConfig({ mode: m.mode, color: rgb }).catch(() => {});
                return;
              }
              const last = lastCommandRef.current;
              if (last) {
                const updated = { ...last, color: rgb, brightness };
                api.broadcastCommand(group, updated).catch(() => {});
                lastCommandRef.current = updated;
              } else {
                api.broadcastCommand(group, { kind: 'color', color: rgb, brightness }).catch(() => {});
              }
            }).catch(() => {});
          }}
          onKill={handleKill}
          deviceCount={deviceCount}
          discordActive={discordActive}
        />
        <main className="tab-content">
          {tab === 'cyber' && <CyberView />}
          {tab === 'command' && <CommandView group={group} color={color} brightness={brightness} speed={speed} onCommandSent={trackCommand} />}
          {tab === 'text' && <TextView group={group} color={color} brightness={brightness} speed={speed} onCommandSent={trackCommand} />}
          {tab === 'mode' && <ModeView />}
          {tab === 'discord' && <StreamView group={group} />}
          {tab === 'toolkit' && (
            <ToolkitView
              group={group}
              color={color}
              onColorChange={(hex) => { setColor(hex); }}
              onCommandSent={trackCommand}
              brightness={brightness}
              onBrightnessChange={handleBrightnessChange}
            />
          )}
        </main>
        <TabBar active={tab} onChange={setTab} />
      </div>
    </AuthGate>
  );
}
