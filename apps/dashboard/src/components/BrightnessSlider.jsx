import { useState } from 'react';

export default function BrightnessSlider({ onCommit }) {
  const [value, setValue] = useState(80);
  return (
    <div className="slider-group">
      <div className="slider-header">
        <span>value</span>
        <span>{value} / 200</span>
      </div>
      <input
        type="range"
        min={0}
        max={200}
        value={value}
        onChange={(e) => setValue(Number(e.target.value))}
        onPointerUp={() => onCommit(value)}
        onKeyUp={() => onCommit(value)}
        className="slider"
      />
    </div>
  );
}
