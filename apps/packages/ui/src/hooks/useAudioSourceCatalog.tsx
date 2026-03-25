import React from "react";

export type AudioInputDeviceOption = {
  deviceId: string;
  label: string;
};

const normalizeAudioInputDevices = (
  devices: MediaDeviceInfo[],
): AudioInputDeviceOption[] => {
  let unnamedCount = 0;

  return devices
    .filter((device) => device.kind === "audioinput")
    .flatMap((device) => {
      const normalizedDeviceId = device.deviceId.trim();
      const rawLabel = device.label.trim();

      if (normalizedDeviceId === "default") {
        return [
          {
            deviceId: normalizedDeviceId,
            label: rawLabel || "Default microphone",
          },
        ];
      }

      if (!normalizedDeviceId) {
        return [];
      }

      if (!rawLabel) {
        unnamedCount += 1;
      }

      return [
        {
          deviceId: normalizedDeviceId,
          label: rawLabel || `Microphone ${unnamedCount || 1}`,
        },
      ];
    });
};

export function useAudioSourceCatalog() {
  const [devices, setDevices] = React.useState<AudioInputDeviceOption[]>([]);
  const [isLoading, setIsLoading] = React.useState(false);
  const [isSettled, setIsSettled] = React.useState(false);

  React.useEffect(() => {
    const mediaDevices =
      typeof navigator !== "undefined" ? navigator.mediaDevices : undefined;

    if (!mediaDevices?.enumerateDevices) {
      setDevices([]);
      setIsSettled(true);
      return;
    }

    let active = true;

    const refreshDevices = async () => {
      if (active) {
        setIsSettled(false);
      }
      setIsLoading(true);
      try {
        const allDevices = await mediaDevices.enumerateDevices();
        if (active) {
          setDevices(normalizeAudioInputDevices(allDevices));
        }
      } catch {
        if (active) {
          setDevices([]);
        }
      } finally {
        if (active) {
          setIsLoading(false);
          setIsSettled(true);
        }
      }
    };

    const handleDeviceChange = () => {
      void refreshDevices();
    };

    void refreshDevices();

    if (typeof mediaDevices.addEventListener === "function") {
      mediaDevices.addEventListener("devicechange", handleDeviceChange);
    } else {
      mediaDevices.ondevicechange = handleDeviceChange;
    }

    return () => {
      active = false;
      if (typeof mediaDevices.removeEventListener === "function") {
        mediaDevices.removeEventListener("devicechange", handleDeviceChange);
      } else if (mediaDevices.ondevicechange === handleDeviceChange) {
        mediaDevices.ondevicechange = null;
      }
    };
  }, []);

  return { devices, isLoading, isSettled };
}
