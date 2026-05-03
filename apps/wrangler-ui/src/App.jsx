import { useCallback, useEffect, useState } from 'react';
import DeviceSelector from './components/DeviceSelector.jsx';
import LiveState from './components/LiveState.jsx';
import ColorTab from './components/ColorTab.jsx';
import EffectTab from './components/EffectTab.jsx';
import TextTab from './components/TextTab.jsx';
import PresetTab from './components/PresetTab.jsx';
import ScheduleTab from './components/ScheduleTab.jsx';
import BrightnessSlider from './components/BrightnessSlider.jsx';
import CyberView from './views/CyberView.jsx';
import { api } from './api.js';

const STORAGE_KEY = 'wrangler.selectedMac';
const TABS = ['Cyber', 'Color', 'Effect', 'Text', 'Preset', 'Schedule'];

export default function App() {
  const [devices, setDevices] = useState([]);
  const [selectedMac, setSelectedMac] = useState(localStorage.getItem(STORAGE_KEY));
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('Cyber');

  const refreshDevices = useCallback(async () => {
    try {
      const { devices } = await api.listDevices();
      setDevices(devices);
      setError(null);
      if (devices.length && !devices.some((d) => d.mac === selectedMac)) {
        const mac = devices[0].mac;
        setSelectedMac(mac);
        localStorage.setItem(STORAGE_KEY, mac);
      }
    } catch (e) { setError(e.message); }
  }, [selectedMac]);

  useEffect(() => { refreshDevices(); }, [refreshDevices]);

  const sendCommand = async (command) => {
    if (!selectedMac) return;
    try {
      await api.sendCommand(selectedMac, command);
      setError(null);
    } catch (e) { setError(e.message); }
  };

  const sendBrightness = (level) => sendCommand({ kind: 'brightness', brightness: level });

  const handleRescan = async () => {
    try {
      const { devices } = await api.rescan();
      setDevices(devices);
    } catch (e) { setError(e.message); }
  };

  return (
    <div className="app-shell">
      <DeviceSelector
        devices={devices}
        selectedMac={selectedMac}
        onSelect={(mac) => { setSelectedMac(mac); localStorage.setItem(STORAGE_KEY, mac); }}
        onRescan={handleRescan}
        onRenamed={refreshDevices}
      />
      {error && <div className="banner-error">{error}</div>}
      <div className="app-body">
        <aside className="status-rail">
          <div className="card">
            <div className="card-header"><span>Live state</span></div>
            {selectedMac
              ? <LiveState selectedMac={selectedMac} />
              : <div className="live-empty">No device selected.</div>}
          </div>
          <div className="card">
            <div className="card-header"><span>Brightness</span></div>
            {selectedMac && <BrightnessSlider onCommit={sendBrightness} />}
          </div>
          <div className="card">
            <div className="card-header"><span>Power</span></div>
            <div className="power-group">
              <button className="btn btn-success" onClick={() => sendCommand({ kind: 'power', on: true })}>On</button>
              <button className="btn btn-danger" onClick={() => sendCommand({ kind: 'power', on: false })}>Off</button>
            </div>
          </div>
        </aside>
        <main className="control-surface">
          <nav className="tabs">
            {TABS.map((t) => (
              <button
                key={t}
                className={t === tab ? 'tab active' : 'tab'}
                onClick={() => setTab(t)}
              >{t}</button>
            ))}
          </nav>
          <div className="tab-panel">
            {tab === 'Cyber' && <CyberView onSend={sendCommand} selectedMac={selectedMac} />}
            {tab === 'Color' && <ColorTab onSend={sendCommand} />}
            {tab === 'Effect' && <EffectTab onSend={sendCommand} />}
            {tab === 'Text' && <TextTab onSend={sendCommand} />}
            {tab === 'Preset' && <PresetTab onSend={sendCommand} />}
            {tab === 'Schedule' && <ScheduleTab onSend={sendCommand} />}
          </div>
        </main>
      </div>
      {!devices.length && (
        <p className="empty-state">No devices found. Click Rescan to search the LAN.</p>
      )}
    </div>
  );
}
