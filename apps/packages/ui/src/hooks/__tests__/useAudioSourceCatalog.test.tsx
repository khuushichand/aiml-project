// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useAudioSourceCatalog } from "../useAudioSourceCatalog";

type MediaDevicesMock = {
  enumerateDevices: ReturnType<typeof vi.fn>;
  addEventListener: ReturnType<typeof vi.fn>;
  removeEventListener: ReturnType<typeof vi.fn>;
  ondevicechange: ((event: Event) => void) | null;
};

const originalMediaDevices = navigator.mediaDevices;

const buildAudioInput = (
  overrides: Partial<MediaDeviceInfo>,
): MediaDeviceInfo =>
  ({
    deviceId: "device-1",
    groupId: "group-1",
    kind: "audioinput",
    label: "USB microphone",
    toJSON: () => ({}),
    ...overrides,
  }) as MediaDeviceInfo;

describe("useAudioSourceCatalog", () => {
  let mediaDevicesMock: MediaDevicesMock;

  beforeEach(() => {
    mediaDevicesMock = {
      enumerateDevices: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      ondevicechange: null,
    };

    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: mediaDevicesMock,
    });
  });

  afterEach(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: originalMediaDevices,
    });
  });

  it("keeps default and filters out non-default devices without real ids", async () => {
    mediaDevicesMock.enumerateDevices.mockResolvedValue([
      buildAudioInput({ deviceId: "default", label: "" }),
      buildAudioInput({ deviceId: "usb-1", label: "" }),
      buildAudioInput({ deviceId: "", label: "" }),
      buildAudioInput({
        kind: "videoinput",
        deviceId: "camera-1",
        label: "HD camera",
      }),
    ]);

    const { result } = renderHook(() => useAudioSourceCatalog());

    expect(result.current.isSettled).toBe(false);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.isSettled).toBe(true);
      expect(result.current.devices).toEqual([
        { deviceId: "default", label: "Default microphone" },
        { deviceId: "usb-1", label: "Microphone 1" },
      ]);
    });
  });

  it("refreshes on devicechange and cleans up the listener on unmount", async () => {
    let resolveSecondEnumerate: ((value: MediaDeviceInfo[]) => void) | null = null
    const secondEnumeratePromise = new Promise<MediaDeviceInfo[]>((resolve) => {
      resolveSecondEnumerate = resolve
    })

    mediaDevicesMock.enumerateDevices
      .mockResolvedValueOnce([
        buildAudioInput({ deviceId: "default", label: "Default microphone" }),
      ])
      .mockReturnValueOnce(secondEnumeratePromise);

    const { result, unmount } = renderHook(() => useAudioSourceCatalog());

    await waitFor(() => {
      expect(result.current.devices).toEqual([
        { deviceId: "default", label: "Default microphone" },
      ]);
    });

    const deviceChangeListener =
      mediaDevicesMock.addEventListener.mock.calls[0]?.[1];
    expect(mediaDevicesMock.addEventListener).toHaveBeenCalledWith(
      "devicechange",
      expect.any(Function),
    );

    await act(async () => {
      void deviceChangeListener?.(new Event("devicechange"));
      await Promise.resolve();
    })

    expect(result.current.isSettled).toBe(false)

    await act(async () => {
      resolveSecondEnumerate?.([
        buildAudioInput({ deviceId: "default", label: "Default microphone" }),
        buildAudioInput({ deviceId: "usb-2", label: "Desk microphone" }),
      ])
      await secondEnumeratePromise
    })

    await waitFor(() => {
      expect(result.current.isSettled).toBe(true)
      expect(result.current.devices).toEqual([
        { deviceId: "default", label: "Default microphone" },
        { deviceId: "usb-2", label: "Desk microphone" },
      ]);
    });

    unmount();

    expect(mediaDevicesMock.removeEventListener).toHaveBeenCalledWith(
      "devicechange",
      deviceChangeListener,
    )
  })
});
