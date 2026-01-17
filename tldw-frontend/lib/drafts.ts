import Dexie, { type Table } from 'dexie';
import type { AssetStatus, Draft, DraftSource } from '@/types/content-review';

export type DraftAssetStorageKind = 'blob' | 'handle' | 'metadata';

export type DraftAssetRecord = {
  draftId: string;
  kind: DraftAssetStorageKind;
  filename: string;
  mime?: string;
  size: number;
  updatedAt: string;
  blob?: Blob;
  fileHandle?: FileSystemFileHandle;
};

export type DraftAssetResolution = {
  assetStatus: AssetStatus;
  assetNote?: string;
  source?: DraftSource;
};

export type PersistDraftFileResult = DraftAssetResolution & {
  storedAs: DraftAssetStorageKind;
};

export type DraftFileLoadResult = DraftAssetResolution & {
  file: File | null;
};

export type DraftRecord = Draft & {
  updatedAt: string;
};

type FilePickerOptions = {
  multiple?: boolean;
};

export type PersistDraftFileParams = {
  draftId: string;
  file: File;
  maxInlineBytes: number;
  fileHandle?: FileSystemFileHandle | null;
};

class DraftsDb extends Dexie {
  assets!: Table<DraftAssetRecord, string>;
  drafts!: Table<DraftRecord, string>;

  constructor() {
    super('tldw-content-review');
    this.version(1).stores({
      assets: '&draftId,updatedAt',
    });
    this.version(2).stores({
      assets: '&draftId,updatedAt',
      drafts: '&id,updatedAt',
    });
  }
}

let dbInstance: DraftsDb | null = null;

const getDb = (): DraftsDb | null => {
  if (typeof window === 'undefined') {
    return null;
  }
  if (!dbInstance) {
    dbInstance = new DraftsDb();
  }
  return dbInstance;
};

const getFileHandleFromFile = (file: File): FileSystemFileHandle | null => {
  const candidate = (file as File & { handle?: FileSystemFileHandle }).handle;
  return candidate || null;
};

const buildFileSource = (file: File): DraftSource => ({
  kind: 'file',
  filename: file.name,
});

export async function persistDraftFileAsset({
  draftId,
  file,
  maxInlineBytes,
  fileHandle,
}: PersistDraftFileParams): Promise<PersistDraftFileResult> {
  const db = getDb();
  const isLarge = file.size > maxInlineBytes;
  const handle = fileHandle ?? getFileHandleFromFile(file);
  const source = buildFileSource(file);

  if (!db) {
    return {
      assetStatus: 'pending',
      assetNote: 'Local draft storage unavailable. Re-select before commit.',
      source,
      storedAs: 'metadata',
    };
  }

  const record: DraftAssetRecord = {
    draftId,
    kind: 'metadata',
    filename: file.name,
    mime: file.type || undefined,
    size: file.size,
    updatedAt: new Date().toISOString(),
  };

  let assetStatus: AssetStatus = 'present';
  let assetNote = 'File stored locally. It will upload on commit.';
  let storedAs: DraftAssetStorageKind = 'metadata';

  if (isLarge) {
    if (handle) {
      record.kind = 'handle';
      record.fileHandle = handle;
      storedAs = 'handle';
      assetNote = 'Large file linked. It will upload on commit.';
    } else {
      record.kind = 'metadata';
      storedAs = 'metadata';
      assetStatus = 'pending';
      assetNote = 'Large file not stored locally. Re-select before commit.';
    }
  } else {
    record.blob = file;
    record.kind = 'blob';
    storedAs = 'blob';
  }

  await db.assets.put(record);

  return {
    assetStatus,
    assetNote,
    source,
    storedAs,
  };
}

/**
 * Draft writes are critical; throw when local storage is unavailable so callers can surface failures.
 */
export async function persistDraft(draft: Draft): Promise<void> {
  const db = getDb();
  if (!db) {
    throw new Error('Local draft storage unavailable. Changes were not saved.');
  }
  const record: DraftRecord = {
    ...draft,
    updatedAt: new Date().toISOString(),
  };
  await db.drafts.put(record);
}

export async function loadDrafts(): Promise<Draft[]> {
  const db = getDb();
  if (!db) {
    return [];
  }
  const records = await db.drafts.orderBy('updatedAt').reverse().toArray();
  return records.map(({ updatedAt: _updatedAt, ...draft }) => draft);
}

export async function getDraftFileAsset(draftId: string): Promise<DraftAssetRecord | null> {
  const db = getDb();
  if (!db) {
    return null;
  }
  return (await db.assets.get(draftId)) || null;
}

const toFile = (blob: Blob, filename: string, mime?: string): File => {
  if (blob instanceof File) {
    return blob;
  }
  return new File([blob], filename, { type: mime || blob.type || 'application/octet-stream' });
};

export async function getDraftFileForUpload(draftId: string): Promise<DraftFileLoadResult> {
  const asset = await getDraftFileAsset(draftId);
  const resolved = await resolveDraftFileAssetStatus(asset);

  if (!asset) {
    return { ...resolved, file: null };
  }

  if (asset.blob instanceof Blob) {
    return {
      ...resolved,
      file: toFile(asset.blob, asset.filename, asset.mime),
    };
  }

  if (asset.fileHandle) {
    try {
      const file = await asset.fileHandle.getFile();
      return {
        ...resolved,
        file,
      };
    } catch (error) {
      console.warn('Failed to access file handle:', error);
      return {
        assetStatus: 'missing',
        assetNote: 'File handle unavailable. Reattach before commit.',
        source: resolved.source,
        file: null,
      };
    }
  }

  return {
    ...resolved,
    file: null,
  };
}

export async function resolveDraftFileAssetStatus(
  asset: DraftAssetRecord | null
): Promise<DraftAssetResolution> {
  if (!asset) {
    return {
      assetStatus: 'missing',
      assetNote: 'Source file missing. Reattach before commit.',
    };
  }

  const source: DraftSource = {
    kind: 'file',
    filename: asset.filename,
  };

  if (asset.blob instanceof Blob) {
    return {
      assetStatus: 'present',
      assetNote: 'File stored locally. It will upload on commit.',
      source,
    };
  }

  if (asset.fileHandle) {
    try {
      // Probe to verify handle is still accessible.
      await asset.fileHandle.getFile();
      return {
        assetStatus: 'present',
        assetNote: 'File linked. It will upload on commit.',
        source,
      };
    } catch (error) {
      console.warn('Failed to access file handle:', error);
      return {
        assetStatus: 'missing',
        assetNote: 'File handle unavailable. Reattach before commit.',
        source,
      };
    }
  }

  if (asset.kind === 'metadata') {
    return {
      assetStatus: 'pending',
      assetNote: 'Large file not stored locally. Re-select before commit.',
      source,
    };
  }

  return {
    assetStatus: 'missing',
    assetNote: 'Source file missing. Reattach before commit.',
    source,
  };
}

export const supportsFileSystemAccess = (): boolean => {
  if (typeof window === 'undefined') {
    return false;
  }
  return typeof (window as Window & { showOpenFilePicker?: unknown }).showOpenFilePicker === 'function';
};

export async function requestFileHandleForFile(
  file: File
): Promise<FileSystemFileHandle | null> {
  if (!supportsFileSystemAccess()) {
    return null;
  }
  const picker = (window as Window & {
    showOpenFilePicker?: (options?: FilePickerOptions) => Promise<FileSystemFileHandle[]>;
  }).showOpenFilePicker;
  if (!picker) {
    return null;
  }
  try {
    const [handle] = await picker({ multiple: false });
    if (!handle) {
      return null;
    }
    const pickedFile = await handle.getFile();
    // Validation only checks name and size; this is a best-effort re-select match.
    if (pickedFile.name !== file.name || pickedFile.size !== file.size) {
      return null;
    }
    return handle;
  } catch {
    // User cancelled or picker failed; return null to signal no handle obtained.
    return null;
  }
}
