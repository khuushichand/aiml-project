export type DraftStatus = 'pending' | 'in_progress' | 'reviewed';
export type AssetStatus = 'present' | 'missing';
export type AssetKind = 'url' | 'file' | 'stream';

export type DraftSource = {
  kind: AssetKind;
  value?: string;
  filename?: string;
};

export type Draft = {
  id: string;
  title: string;
  status: DraftStatus;
  mediaType: string;
  content: string;
  keywords: string[];
  assetStatus: AssetStatus;
  source?: DraftSource;
  assetNote?: string;
};
