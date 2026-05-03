async function jsonOrThrow(res) {
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  listDevices: async () => jsonOrThrow(await fetch('/api/devices')),
  rescan: async () => jsonOrThrow(await fetch('/api/scan', { method: 'POST' })),
  getState: async (mac) =>
    jsonOrThrow(await fetch(`/api/devices/${encodeURIComponent(mac)}/state`)),
  rename: async (mac, name) =>
    jsonOrThrow(
      await fetch(`/api/devices/${encodeURIComponent(mac)}/name`, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ name }),
      }),
    ),
  sendCommand: async (mac, command) =>
    jsonOrThrow(
      await fetch(`/api/devices/${encodeURIComponent(mac)}/commands`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(command),
      }),
    ),
  listEffects: async () => jsonOrThrow(await fetch('/api/effects')),
  listPresets: async () => jsonOrThrow(await fetch('/api/presets')),
  listEmoji: async () => jsonOrThrow(await fetch('/api/emoji')),
  listSchedule: async () => jsonOrThrow(await fetch('/api/schedule/all')),
  getNextSession: async () => jsonOrThrow(await fetch('/api/schedule/next')),
  getCurrentSession: async () => jsonOrThrow(await fetch('/api/schedule/current')),
};
