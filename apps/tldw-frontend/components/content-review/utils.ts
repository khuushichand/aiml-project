import type { DraftStatus } from '@web/types/content-review';

export const formatStatus = (status: DraftStatus) => status.replace('_', ' ');
