import type { DraftStatus } from '@/types/content-review';

export const formatStatus = (status: DraftStatus) => status.replace('_', ' ');
