import { describe, expect, it } from "vitest"

import { parseTemplateToComposerAst } from "../composer-roundtrip"

describe("composer-roundtrip", () => {
  it("uses deterministic node ids when parsing identical content repeatedly", () => {
    const content = [
      "# {{ title }}",
      "",
      "{% for item in items %}",
      "## {{ item.title }}",
      "{% endfor %}",
      "",
      "Footer copy"
    ].join("\n")

    const first = parseTemplateToComposerAst(content)
    const second = parseTemplateToComposerAst(content)

    expect(first.nodes.map((node) => node.id)).toEqual(second.nodes.map((node) => node.id))
  })
})
