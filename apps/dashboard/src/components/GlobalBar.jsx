import { useCallback, useRef, useState } from 'react';
import SettingsSheet from './SettingsSheet.jsx';

function hslToHex(h, s, l) {
  s /= 100;
  l /= 100;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => {
    const k = (n + h / 30) % 12;
    const c = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * c).toString(16).padStart(2, '0');
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function pickColorFromEvent(e, canvas) {
  const rect = canvas.getBoundingClientRect();
  const x = (e.clientX ?? e.touches[0].clientX) - rect.left;
  const y = (e.clientY ?? e.touches[0].clientY) - rect.top;
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const dx = x - cx;
  const dy = y - cy;
  const angle = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
  const dist = Math.min(Math.sqrt(dx * dx + dy * dy) / cx, 1);
  // Hue from angle, saturation from distance, lightness fixed at 50%
  // But near center = white (low saturation)
  return hslToHex(angle, dist * 100, 50);
}

export default function GlobalBar({
  group,
  onGroupChange,
  groups,
  brightness,
  onBrightnessChange,
  speed,
  onSpeedChange,
  color,
  onColorChange,
  onKill,
  deviceCount,
  discordActive,
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const canvasRef = useRef(null);

  const drawWheel = useCallback((canvas) => {
    if (!canvas) return;
    canvasRef.current = canvas;
    const ctx = canvas.getContext('2d');
    const size = canvas.width;
    const cx = size / 2;
    const cy = size / 2;
    const radius = size / 2;

    for (let angle = 0; angle < 360; angle++) {
      const startAngle = (angle - 1) * Math.PI / 180;
      const endAngle = (angle + 1) * Math.PI / 180;
      const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
      gradient.addColorStop(0, `hsl(${angle}, 0%, 100%)`);
      gradient.addColorStop(0.5, `hsl(${angle}, 100%, 50%)`);
      gradient.addColorStop(1, `hsl(${angle}, 100%, 20%)`);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, radius, startAngle, endAngle);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();
    }
  }, []);

  const handleWheelClick = (e) => {
    const hex = pickColorFromEvent(e, canvasRef.current);
    onColorChange(hex);
    setPickerOpen(false);
  };

  return (
    <div className="global-bar">
      {/* Status line */}
      <div className="global-status">
        <span className="global-status-devices">
          {deviceCount} device{deviceCount !== 1 ? 's' : ''}
        </span>
        <span className="global-status-right">
          <span
            className={`global-discord-dot ${discordActive ? 'on' : 'off'}`}
            title={discordActive ? 'Discord connected' : 'Discord offline'}
          />
          <button className="global-gear-btn" onClick={() => setSettingsOpen(true)} title="Settings">
            {'\u2699'}
          </button>
          <button className="global-kill-btn" onClick={onKill}>
            KILL
          </button>
        </span>
      </div>

      {/* Group pills */}
      <div className="global-groups">
        {groups.map((g) => (
          <button
            key={g}
            className={`group-pill ${group === g ? 'active' : ''}`}
            onClick={() => onGroupChange(g)}
          >
            {g}
          </button>
        ))}
      </div>

      {/* Brightness + speed + color dot */}
      <div className="global-controls-row">
        <input
          type="range"
          className="global-brightness-slider"
          min={0}
          max={200}
          value={brightness}
          onChange={(e) => onBrightnessChange(Number(e.target.value))}
          title={`Brightness: ${brightness}`}
        />
        <input
          type="range"
          className="global-speed-slider"
          min={0}
          max={240}
          value={speed}
          onChange={(e) => onSpeedChange(Number(e.target.value))}
          title={`Text speed: ${speed}`}
        />
        <button
          className="global-color-dot"
          style={{ background: color }}
          onClick={() => setPickerOpen((o) => !o)}
          title="Pick color"
        />
      </div>

      {/* Color wheel overlay */}
      {pickerOpen && (
        <div className="color-wheel-overlay" onClick={() => setPickerOpen(false)}>
          <div className="color-wheel-container" onClick={(e) => e.stopPropagation()}>
            <canvas
              ref={drawWheel}
              width={280}
              height={280}
              className="color-wheel-canvas"
              onClick={handleWheelClick}
            />
            <div className="color-wheel-preview" style={{ background: color }} />
          </div>
        </div>
      )}

      <SettingsSheet open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
