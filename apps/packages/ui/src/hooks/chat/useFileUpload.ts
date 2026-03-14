import { generateID } from "@/db/dexie/helpers";
import { type UploadedFile } from "@/db/dexie/types";

const toText = (value: unknown, fallback = ""): string =>
  typeof value === "string" && value.trim().length > 0 ? value : fallback;

export type UseFileUploadOptions = {
  maxContextFileSizeBytes: number;
  maxContextFileSizeLabel: string;
  notification: {
    error: (opts: { message: string; description: string }) => void;
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  t: (...args: any[]) => unknown;
  uploadedFiles: UploadedFile[];
  setUploadedFiles: (files: UploadedFile[]) => void;
  contextFiles: UploadedFile[];
  setContextFiles: (files: UploadedFile[]) => void;
};

export const useFileUpload = ({
  maxContextFileSizeBytes,
  maxContextFileSizeLabel,
  notification,
  t,
  uploadedFiles,
  setUploadedFiles,
  contextFiles,
  setContextFiles,
}: UseFileUploadOptions) => {
  const handleFileUpload = async (file: File) => {
    try {
      const isImage = file.type.startsWith("image/");

      if (isImage) {
        return file;
      }

      if (file.size > maxContextFileSizeBytes) {
        notification.error({
          message: toText(
            t("upload.fileTooLargeTitle", "File Too Large"),
            "File Too Large",
          ),
          description: toText(
            t("upload.fileTooLargeDescription", {
              defaultValue: "File size must be less than {{size}}",
              size: maxContextFileSizeLabel,
            } as any),
            `File size must be less than ${maxContextFileSizeLabel}`,
          ),
        });
        return;
      }

      const fileId = generateID();

      const { processFileUpload } = await import("~/utils/file-processor");
      const source = await processFileUpload(file);

      const uploadedFile: UploadedFile = {
        id: fileId,
        filename: file.name,
        type: file.type,
        content: source.content,
        size: file.size,
        uploadedAt: Date.now(),
        processed: false,
      };

      setUploadedFiles([...uploadedFiles, uploadedFile]);
      setContextFiles([...contextFiles, uploadedFile]);

      return file;
    } catch (error) {
      console.error("Error uploading file:", error);
      notification.error({
        message: toText(
          t("upload.uploadFailedTitle", "Upload Failed"),
          "Upload Failed",
        ),
        description: toText(
          t(
            "upload.uploadFailedDescription",
            "Failed to upload file. Please try again.",
          ),
          "Failed to upload file. Please try again.",
        ),
      });
      throw error;
    }
  };

  const removeUploadedFile = async (fileId: string) => {
    setUploadedFiles(uploadedFiles.filter((f) => f.id !== fileId));
    setContextFiles(contextFiles.filter((f) => f.id !== fileId));
  };

  const clearUploadedFiles = () => {
    setUploadedFiles([]);
  };

  return {
    handleFileUpload,
    removeUploadedFile,
    clearUploadedFiles,
  };
};
