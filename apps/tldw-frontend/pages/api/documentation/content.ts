import type { NextApiRequest, NextApiResponse } from "next"

import {
  readDocumentationContent,
  type DocumentationSource,
} from "@web/lib/documentation"

const isDocumentationSource = (value: string): value is DocumentationSource =>
  value === "extension" || value === "server"

const getSingleQueryValue = (value: string | string[] | undefined) =>
  Array.isArray(value) ? value[0] : value

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== "GET") {
    res.setHeader("Allow", "GET")
    return res.status(405).json({ error: "Method not allowed." })
  }

  const source = getSingleQueryValue(req.query.source)
  const relativePath = getSingleQueryValue(req.query.relativePath)

  if (!source || !isDocumentationSource(source) || !relativePath) {
    return res.status(400).json({ error: "Missing or invalid documentation query." })
  }

  try {
    const content = await readDocumentationContent(source, relativePath)
    return res.status(200).json({ content })
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Unable to load documentation content."
    const status = /invalid|unsupported/i.test(message) ? 400 : 404
    return res.status(status).json({ error: message })
  }
}
