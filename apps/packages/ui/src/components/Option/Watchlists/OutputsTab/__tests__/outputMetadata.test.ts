import { describe, expect, it } from "vitest"
import {
  buildDeliveryDisclosureSummary,
  buildRegenerateOutputRequest,
  getDeliveryStatusColor,
  getDeliveryStatusLabel,
  getOutputArtifactLabel,
  getOutputArtifactTagColor,
  getOutputDeliveryStatuses,
  getOutputFileExtension,
  getOutputMimeType,
  getOutputTemplateName,
  getOutputTemplateVersion,
  isAudioOutput
} from "../outputMetadata"

describe("outputMetadata helpers", () => {
  it("builds regenerate request with template version when template name is set", () => {
    const payload = buildRegenerateOutputRequest(
      {
        run_id: 99,
        type: "brief"
      },
      {
        title: "  Daily Digest  ",
        templateName: "digest",
        templateVersion: 3
      }
    )

    expect(payload).toEqual({
      run_id: 99,
      type: "brief",
      title: "Daily Digest",
      template_name: "digest",
      template_version: 3
    })
  })

  it("drops template version when template name is empty", () => {
    const payload = buildRegenerateOutputRequest(
      {
        run_id: 7,
        type: "brief"
      },
      {
        title: "Digest",
        templateName: "  ",
        templateVersion: 5
      }
    )

    expect(payload).toEqual({
      run_id: 7,
      type: "brief",
      title: "Digest"
    })
  })

  it("normalizes deliveries from array and object fallback shapes", () => {
    const fromArray = getOutputDeliveryStatuses({
      deliveries: [
        { channel: "email", status: "sent" },
        { channel: "chatbook", status: "stored", message: "generated" }
      ]
    })
    const fromObject = getOutputDeliveryStatuses({
      deliveries: {
        email: { status: "partial", reason: "1 invalid recipient" },
        chatbook: "stored"
      }
    })

    expect(fromArray).toEqual([
      { channel: "email", status: "sent", detail: undefined },
      { channel: "chatbook", status: "stored", detail: "generated" }
    ])
    expect(fromObject).toEqual([
      { channel: "email", status: "partial", detail: "1 invalid recipient" },
      { channel: "chatbook", status: "stored" }
    ])
  })

  it("extracts template metadata defensively", () => {
    expect(
      getOutputTemplateName({ template_name: "digest-template", template_version: "4" })
    ).toBe("digest-template")
    expect(getOutputTemplateVersion({ template_version: "4" })).toBe(4)
    expect(getOutputTemplateVersion({ template_version: 0 })).toBeUndefined()
  })

  it("maps delivery status colors", () => {
    expect(getDeliveryStatusColor("sent")).toBe("green")
    expect(getDeliveryStatusColor("partial")).toBe("gold")
    expect(getDeliveryStatusColor("pending")).toBe("blue")
    expect(getDeliveryStatusColor("failed")).toBe("red")
    expect(getDeliveryStatusColor("mystery")).toBe("default")
  })

  it("normalizes delivery status labels", () => {
    expect(getDeliveryStatusLabel("sent")).toBe("Sent")
    expect(getDeliveryStatusLabel("in_progress")).toBe("In progress")
    expect(getDeliveryStatusLabel("failed")).toBe("Failed")
    expect(getDeliveryStatusLabel("mystery")).toBe("mystery")
  })

  it("builds delivery disclosure summary for collapsed and expanded views", () => {
    const deliveries = [
      { channel: "email", status: "sent" },
      { channel: "chatbook", status: "stored" },
      { channel: "webhook", status: "failed", detail: "timeout" }
    ]

    expect(buildDeliveryDisclosureSummary(deliveries)).toEqual({
      visible: [{ channel: "email", status: "sent" }],
      hidden: [
        { channel: "chatbook", status: "stored" },
        { channel: "webhook", status: "failed", detail: "timeout" }
      ]
    })

    expect(buildDeliveryDisclosureSummary(deliveries, { maxVisible: 3 })).toEqual({
      visible: deliveries,
      hidden: []
    })
  })

  it("classifies audio outputs and derives mime + extension", () => {
    const audioOutput = { format: "mp3", type: "tts_audio" }
    const markdownOutput = { format: "md", type: "briefing" }

    expect(isAudioOutput(audioOutput)).toBe(true)
    expect(isAudioOutput(markdownOutput)).toBe(false)
    expect(getOutputMimeType(audioOutput.format)).toBe("audio/mpeg")
    expect(getOutputMimeType(markdownOutput.format)).toBe("text/markdown")
    expect(getOutputFileExtension(audioOutput)).toBe("mp3")
    expect(getOutputFileExtension(markdownOutput)).toBe("md")
  })

  it("returns artifact labels and tag colors by output kind", () => {
    expect(getOutputArtifactLabel({ format: "mp3", type: "tts_audio" })).toBe("Audio")
    expect(getOutputArtifactTagColor({ format: "mp3", type: "tts_audio" })).toBe("purple")

    expect(getOutputArtifactLabel({ format: "html", type: "briefing" })).toBe("HTML")
    expect(getOutputArtifactTagColor({ format: "html", type: "briefing" })).toBe("blue")

    expect(getOutputArtifactLabel({ format: "md", type: "briefing" })).toBe("Markdown")
    expect(getOutputArtifactTagColor({ format: "md", type: "briefing" })).toBe("green")
  })
})
