export const isYouTube = (u: string): boolean => {
  try {
    const url = new URL(u);
    const host = url.hostname.toLowerCase();
    const h = host.startsWith('www.') ? host.slice(4) : host;
    return /(^|\.)youtube\.com$/.test(h) || h === 'youtu.be' || h === 'm.youtube.com';
  } catch {
    return false;
  }
};

export const isYouTubeFeedUrl = (u: string): boolean => {
  try {
    const url = new URL(u);
    if (!url.pathname.toLowerCase().startsWith('/feeds/videos.xml')) return false;
    const qs = url.searchParams;
    return qs.has('channel_id') || qs.has('playlist_id') || qs.has('user');
  } catch {
    return false;
  }
};

export const toCanonicalYouTubeFeed = (u: string): string | null => {
  try {
    const parsed = new URL(u);
    const list = parsed.searchParams.get('list');
    if (list) {
      return `https://www.youtube.com/feeds/videos.xml?playlist_id=${list}`;
    }
    const parts = parsed.pathname.split('/').filter(Boolean);
    const i = parts.findIndex((p) => p.toLowerCase() === 'channel');
    if (i >= 0 && parts[i + 1]) {
      const cid = parts[i + 1];
      return `https://www.youtube.com/feeds/videos.xml?channel_id=${cid}`;
    }
    return null;
  } catch {
    return null;
  }
};

