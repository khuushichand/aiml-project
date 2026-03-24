import type { NextApiRequest, NextApiResponse } from "next"

import { listDocumentationManifest } from "@web/lib/documentation"

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET")
    return res.status(405).json({ error: "Method not allowed." })
  }

  try {
    const docsBySource = await listDocumentationManifest()
    return res.status(200).json({ docsBySource })
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unable to load documentation manifest."
    return res.status(500).json({ error: message })
  }
}
