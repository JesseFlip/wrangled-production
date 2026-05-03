const TOKEN_KEY = 'wrangled.token';

function getHeaders() {
  const headers = { 'content-type': 'application/json' };
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) headers['authorization'] = `Bearer ${token}`;
  return headers;
}

async function jsonOrThrow(res) {
  if (res.status === 401) throw new Error('AUTH_REQUIRED');
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  listDevices: async () => jsonOrThrow(await fetch('/api/devices', { headers: getHeaders() })),
  getState: async (mac) => jsonOrThrow(await fetch(`/api/devices/${encodeURIComponent(mac)}/state`, { headers: getHeaders() })),
  sendCommand: async (mac, command) => jsonOrThrow(await fetch(`/api/devices/${encodeURIComponent(mac)}/commands`, {
    method: 'POST', headers: getHeaders(), body: JSON.stringify(command),
  })),
  rename: async (mac, name) => jsonOrThrow(await fetch(`/api/devices/${encodeURIComponent(mac)}/name`, {
    method: 'PUT', headers: getHeaders(), body: JSON.stringify({ name }),
  })),
  rescan: async () => jsonOrThrow(await fetch('/api/scan', { method: 'POST', headers: getHeaders() })),
  listEffects: async () => jsonOrThrow(await fetch('/api/effects', { headers: getHeaders() })),
  listPresets: async () => jsonOrThrow(await fetch('/api/presets', { headers: getHeaders() })),
  listEmoji: async () => jsonOrThrow(await fetch('/api/emoji', { headers: getHeaders() })),
  listWranglers: async () => jsonOrThrow(await fetch('/api/wranglers', { headers: getHeaders() })),
  recentCommands: async (limit = 100) => jsonOrThrow(await fetch(`/api/commands/recent?limit=${limit}`, { headers: getHeaders() })),

  // Matrix mode
  getMode: async () => jsonOrThrow(await fetch('/api/mode', { headers: getHeaders() })),
  setMode: async (body) => jsonOrThrow(await fetch('/api/mode', {
    method: 'PUT', headers: getHeaders(), body: JSON.stringify(body),
  })),
  updateModeConfig: async (body) => jsonOrThrow(await fetch('/api/mode', {
    method: 'PATCH', headers: getHeaders(), body: JSON.stringify(body),
  })),
  goIdle: async () => jsonOrThrow(await fetch('/api/mode/idle', { method: 'POST', headers: getHeaders() })),

  // Schedule
  listSchedule: async () => jsonOrThrow(await fetch('/api/schedule/all', { headers: getHeaders() })),
  getCurrentSession: async () => jsonOrThrow(await fetch('/api/schedule/current', { headers: getHeaders() })),
  getNextSession: async () => jsonOrThrow(await fetch('/api/schedule/next', { headers: getHeaders() })),

  // Moderation
  modConfig: async () => jsonOrThrow(await fetch('/api/mod/config', { headers: getHeaders() })),
  modUpdateConfig: async (updates) => jsonOrThrow(await fetch('/api/mod/config', {
    method: 'PUT', headers: getHeaders(), body: JSON.stringify(updates),
  })),
  modEmergencyOff: async () => jsonOrThrow(await fetch('/api/mod/emergency-off', { method: 'POST', headers: getHeaders() })),
  modHistory: async (limit = 100) => jsonOrThrow(await fetch(`/api/mod/history?limit=${limit}`, { headers: getHeaders() })),
  modDeviceLocks: async () => jsonOrThrow(await fetch('/api/mod/devices', { headers: getHeaders() })),
  modLockDevice: async (mac) => jsonOrThrow(await fetch(`/api/mod/device/${encodeURIComponent(mac)}/lock`, { method: 'POST', headers: getHeaders() })),
  modUnlockDevice: async (mac) => jsonOrThrow(await fetch(`/api/mod/device/${encodeURIComponent(mac)}/unlock`, { method: 'POST', headers: getHeaders() })),
  modBanned: async () => jsonOrThrow(await fetch('/api/mod/banned', { headers: getHeaders() })),
  modBan: async (userId, username, reason) => jsonOrThrow(await fetch('/api/mod/banned', {
    method: 'POST', headers: getHeaders(), body: JSON.stringify({ user_id: userId, username, reason }),
  })),
  modUnban: async (userId) => jsonOrThrow(await fetch(`/api/mod/banned/${encodeURIComponent(userId)}`, { method: 'DELETE', headers: getHeaders() })),

  // Quick texts (persisted canned messages)
  listQuickTexts: async () => jsonOrThrow(await fetch('/api/mod/quick-texts', { headers: getHeaders() })),
  addQuickText: async (text) => jsonOrThrow(await fetch('/api/mod/quick-texts', {
    method: 'POST', headers: getHeaders(), body: JSON.stringify({ text }),
  })),
  removeQuickText: async (text) => jsonOrThrow(await fetch(`/api/mod/quick-texts/${encodeURIComponent(text)}`, { method: 'DELETE', headers: getHeaders() })),

  // Device group tags
  listDeviceGroups: async () => jsonOrThrow(await fetch('/api/mod/device-groups', { headers: getHeaders() })),
  setDeviceGroup: async (mac, group) => jsonOrThrow(await fetch(`/api/mod/device-groups/${encodeURIComponent(mac)}`, {
    method: 'PUT', headers: getHeaders(), body: JSON.stringify({ group }),
  })),

  // Groups
  listGroups: async () => jsonOrThrow(await fetch('/api/groups', { headers: getHeaders() })),
  createGroup: async (name, macs) => jsonOrThrow(await fetch('/api/groups', {
    method: 'POST', headers: getHeaders(), body: JSON.stringify({ name, macs }),
  })),
  deleteGroup: async (name) => jsonOrThrow(await fetch(`/api/groups/${encodeURIComponent(name)}`, { method: 'DELETE', headers: getHeaders() })),

  /**
   * Send a command to all devices in a group.
   * "all" fetches all devices. Otherwise resolves group MACs.
   */
  broadcastCommand: async (group, command) => {
    const { devices } = await api.listDevices();
    let macs;
    if (group === 'all') {
      macs = devices.map((d) => d.mac);
    } else {
      // Check persisted device group tags
      const dgs = await api.listDeviceGroups().catch(() => ({ groups: [] }));
      const taggedMacs = (dgs.groups || []).filter((g) => g.group === group).map((g) => g.mac);
      macs = taggedMacs.length > 0 ? taggedMacs : [];
    }
    let ok = 0;
    let failed = 0;
    const errors = [];
    for (const mac of macs) {
      try {
        await api.sendCommand(mac, command);
        ok++;
      } catch (err) {
        failed++;
        errors.push(`${mac}: ${err.message}`);
      }
    }
    return { ok, failed, errors };
  },
};

/**
 * Subscribe to the SSE command stream.
 * Returns an EventSource. Call .close() to disconnect.
 */
export function subscribeStream(onEvent) {
  const token = localStorage.getItem(TOKEN_KEY);
  const url = `/api/stream${token ? `?token=${encodeURIComponent(token)}` : ''}`;
  const source = new EventSource(url);
  source.addEventListener('command', (e) => {
    try {
      onEvent(JSON.parse(e.data));
    } catch {
      // ignore parse errors
    }
  });
  return source;
}
