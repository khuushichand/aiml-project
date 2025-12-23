import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { apiClient, getApiBaseUrl, buildAuthHeaders } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import type { MediaDetailResponse } from '@/types/api';

export default function MediaViewPage() {
  const router = useRouter();
  const { id } = router.query;
  const { show } = useToast();

  const [media, setMedia] = useState<MediaDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  // Fetch media details
  const loadMedia = useCallback(async (mediaId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<MediaDetailResponse>(`/media/${mediaId}`);
      setMedia(data);

      if (!data.has_original_file) {
        setError('No original file available for this media item.');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load media details';
      setError(message);
      show({ title: 'Error', description: message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [show]);

  // Fetch the PDF as a blob for authenticated viewing
  const loadPdf = useCallback(async (mediaId: string) => {
    setPdfLoading(true);
    try {
      const baseUrl = getApiBaseUrl();
      const headers = buildAuthHeaders('GET');

      const response = await fetch(`${baseUrl}/media/${mediaId}/file`, {
        method: 'GET',
        headers,
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch PDF: ${response.status} ${response.statusText}`);
      }

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      setPdfBlobUrl(blobUrl);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load PDF';
      setError(message);
      show({ title: 'PDF Load Error', description: message, variant: 'danger' });
    } finally {
      setPdfLoading(false);
    }
  }, [show]);

  useEffect(() => {
    if (id && typeof id === 'string') {
      loadMedia(id);
    }
  }, [id, loadMedia]);

  useEffect(() => {
    if (media?.has_original_file && id && typeof id === 'string') {
      loadPdf(id);
    }
  }, [media, id, loadPdf]);

  // Cleanup blob URL on unmount
  useEffect(() => {
    return () => {
      if (pdfBlobUrl) {
        URL.revokeObjectURL(pdfBlobUrl);
      }
    };
  }, [pdfBlobUrl]);

  const openInNewTab = useCallback(() => {
    if (pdfBlobUrl) {
      window.open(pdfBlobUrl, '_blank');
    }
  }, [pdfBlobUrl]);

  const downloadPdf = useCallback(() => {
    if (pdfBlobUrl && media) {
      const link = document.createElement('a');
      link.href = pdfBlobUrl;
      link.download = `${media.source?.title || 'document'}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
  }, [pdfBlobUrl, media]);

  return (
    <Layout>
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="flex items-center justify-between border-b bg-white px-4 py-3">
          <div className="flex items-center space-x-4">
            <Button variant="secondary" onClick={() => router.push('/media')}>
              Back to Media
            </Button>
            <h1 className="text-lg font-semibold text-gray-900 truncate max-w-md">
              {loading ? 'Loading...' : media?.source?.title || 'Untitled'}
            </h1>
          </div>
          <div className="flex items-center space-x-2">
            {pdfBlobUrl && (
              <>
                <Button variant="secondary" onClick={openInNewTab}>
                  Open in New Tab
                </Button>
                <Button variant="secondary" onClick={downloadPdf}>
                  Download
                </Button>
              </>
            )}
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-hidden bg-gray-100">
          {loading && (
            <div className="flex h-full items-center justify-center">
              <div className="text-gray-500">Loading media details...</div>
            </div>
          )}

          {error && !loading && (
            <div className="flex h-full flex-col items-center justify-center space-y-4">
              <div className="rounded-lg bg-red-50 p-6 text-center">
                <div className="text-red-800">{error}</div>
              </div>
              <Button variant="secondary" onClick={() => router.push('/media')}>
                Return to Media
              </Button>
            </div>
          )}

          {pdfLoading && !error && (
            <div className="flex h-full items-center justify-center">
              <div className="text-gray-500">Loading PDF...</div>
            </div>
          )}

          {pdfBlobUrl && !error && (
            <iframe
              src={pdfBlobUrl}
              className="h-full w-full border-0"
              title={media?.source?.title || 'PDF Viewer'}
            />
          )}
        </div>
      </div>
    </Layout>
  );
}
