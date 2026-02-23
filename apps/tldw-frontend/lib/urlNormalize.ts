const normalizeHost = (host: string): string => (host.startsWith('www.') ? host.slice(4) : host);

const isYouTubeHost = (host: string): boolean => {
  const h = normalizeHost(host.toLowerCase());
  return /(^|\.)youtube\.com$/.test(h) || h === 'youtu.be';
};

/**
 * Checks if the given URL is from YouTube (youtube.com or youtu.be).
 * @param u - The URL string to check
 * @returns true if the URL is from YouTube, false if invalid or non-YouTube
 */
export const isYouTube = (u: string): boolean => {
  try {
    const url = new URL(u);
    return isYouTubeHost(url.hostname);
  } catch {
    return false;
  }
};

/**
 * Checks if the given URL is a valid YouTube feed URL.
 * Feed URLs must have the path /feeds/videos.xml and at least one of:
 * channel_id, playlist_id, or user query parameters.
 * @param u - The URL string to check
 * @returns true if the URL is a YouTube feed URL, false otherwise
 */
export const isYouTubeFeedUrl = (u: string): boolean => {
  try {
    const url = new URL(u);
    if (!isYouTubeHost(url.hostname)) return false;
    if (!url.pathname.toLowerCase().startsWith('/feeds/videos.xml')) return false;
    const qs = url.searchParams;
    return qs.has('channel_id') || qs.has('playlist_id') || qs.has('user');
  } catch {
    return false;
  }
};

/**
 * Converts a YouTube URL to its canonical feed URL format.
 * Supports URLs with 'list' query parameter or '/channel/' path segments.
 * @param u - The YouTube URL to canonicalize
 * @returns The canonical feed URL, or null if the URL cannot be canonicalized
 */
export const toCanonicalYouTubeFeed = (u: string): string | null => {
  try {
    const parsed = new URL(u);
    if (!isYouTubeHost(parsed.hostname)) return null;
    const list = parsed.searchParams.get('list');
    if (list) {
      const cleanedList = list.trim();
      if (cleanedList) {
        return `https://www.youtube.com/feeds/videos.xml?playlist_id=${encodeURIComponent(cleanedList)}`;
      }
    }
    const parts = parsed.pathname.split('/').filter(Boolean);
    const i = parts.findIndex((p) => p.toLowerCase() === 'channel');
    if (i >= 0 && parts[i + 1]) {
      const cid = parts[i + 1].trim();
      if (cid) {
        return `https://www.youtube.com/feeds/videos.xml?channel_id=${encodeURIComponent(cid)}`;
      }
    }
    return null;
  } catch {
    return null;
  }
};
