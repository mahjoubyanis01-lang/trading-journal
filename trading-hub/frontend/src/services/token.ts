// Loopback API token (local hardening). The desktop launcher opens the window
// at /?token=XXXX; we capture it once, persist it for the session, and send it
// on every API/WebSocket call. In plain dev (no token) everything still works.
const KEY = 'th_api_token';

function capture(): string {
  try {
    const url = new URL(window.location.href);
    const fromUrl = url.searchParams.get('token');
    if (fromUrl) {
      sessionStorage.setItem(KEY, fromUrl);
      // Clean the token out of the visible URL.
      url.searchParams.delete('token');
      window.history.replaceState({}, '', url.toString());
      return fromUrl;
    }
    return sessionStorage.getItem(KEY) ?? '';
  } catch {
    return '';
  }
}

let token = capture();

export function getToken(): string {
  return token;
}

export function setToken(value: string): void {
  token = value;
  try {
    sessionStorage.setItem(KEY, value);
  } catch {
    /* ignore */
  }
}
