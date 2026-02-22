import { CharGrid } from "../../engine/CharGrid";
import type { SplashEffect } from "../../engine/types";

const CODE_LINES = [
  "import { tldw } from '@tldw/core';",
  "const server = new FastAPI({ debug: true });",
  "async function processMedia(input: MediaFile) {",
  "  const chunks = await splitIntoChunks(input);",
  "  for (const chunk of chunks) {",
  "    const transcript = await whisper.transcribe(chunk);",
  "    await db.store(transcript);",
  "  }",
  "  return { status: 'complete' };",
  "}",
  "",
  "server.post('/api/v1/media', async (req) => {",
  "  const result = await processMedia(req.body);",
  "  return Response.json(result);",
  "});",
  "",
  "const embeddings = await generateEmbeddings(text);",
  "const similar = await vectorStore.search(query, { k: 10 });",
  "const context = similar.map(r => r.content).join('\\n');",
  "const answer = await llm.chat({ context, question });",
  "",
  "// RAG pipeline initialized",
  "const pipeline = new UnifiedRAGPipeline({",
  "  retriever: hybridSearch,",
  "  reranker: crossEncoder,",
  "  cache: semanticCache,",
  "});",
  "",
  "export default server.listen(8000);",
  "console.log('tldw server ready on :8000');",
];

const KEYWORD_COLOR = "#ff79c6";
const STRING_COLOR = "#f1fa8c";
const COMMENT_COLOR = "#6272a4";
const DEFAULT_COLOR = "#88cc88";

export default class CodeScroll implements SplashEffect {
  private grid = new CharGrid(80, 24);
  private w = 0;
  private h = 0;
  private elapsed = 0;

  init(_ctx: CanvasRenderingContext2D, width: number, height: number): void {
    this.w = width;
    this.h = height;
    this.elapsed = 0;
  }

  update(elapsed: number, _dt: number): void {
    this.elapsed = elapsed;
  }

  private lineColor(line: string): string {
    if (line.trimStart().startsWith("//")) return COMMENT_COLOR;
    if (/\b(import|export|const|async|function|for|return|await|default|new)\b/.test(line)) return KEYWORD_COLOR;
    if (/['"`]/.test(line)) return STRING_COLOR;
    return DEFAULT_COLOR;
  }

  render(ctx: CanvasRenderingContext2D): void {
    const grid = this.grid;
    grid.clear();

    const scrollOffset = Math.floor(this.elapsed / 300);
    const totalLines = CODE_LINES.length;

    for (let row = 0; row < 24; row++) {
      const lineIdx = (scrollOffset + row) % totalLines;
      const line = CODE_LINES[lineIdx];
      const color = this.lineColor(line);
      const lineNum = String((scrollOffset + row) % 999 + 1).padStart(3, " ");
      grid.writeString(0, row, lineNum, "#555555");
      grid.setCell(3, row, "|", "#333333");
      grid.writeString(5, row, line.slice(0, 74), color);
    }

    // Title overlay
    const cy = 11;
    const title = "  tldw  ";
    const pad = " ".repeat(title.length);
    grid.writeCentered(cy - 1, pad, "#000000");
    grid.writeCentered(cy, title, "#ffffff");
    grid.writeCentered(cy + 1, pad, "#000000");

    const cellW = this.w / grid.cols;
    const cellH = this.h / grid.rows;
    grid.renderToCanvas(ctx, cellW, cellH);
  }

  reset(): void {
    this.elapsed = 0;
    this.grid.clear();
  }

  dispose(): void {
    this.grid.clear();
  }
}
