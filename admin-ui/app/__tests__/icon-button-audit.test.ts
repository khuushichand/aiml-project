import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

const ROOT_DIRS = ['app', 'components'];
const SOURCE_EXTENSIONS = new Set(['.tsx', '.ts']);
const TEST_FILE_PATTERN = /\.(test|spec)\.tsx?$/;

const collectSourceFiles = (directory: string, out: string[]) => {
  const entries = readdirSync(directory, { withFileTypes: true });
  entries.forEach((entry) => {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '.next') return;
      collectSourceFiles(fullPath, out);
      return;
    }

    const extension = path.extname(entry.name);
    if (!SOURCE_EXTENSIONS.has(extension)) return;
    if (TEST_FILE_PATTERN.test(entry.name)) return;
    out.push(fullPath);
  });
};

const stripJsxToText = (value: string): string => value
  .replace(/<[^>]+>/g, ' ')
  .replace(/\{[^}]*\}/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

const hasStringLiteralText = (value: string): boolean => (
  /['"`][^'"`]*[A-Za-z0-9][^'"`]*['"`]/.test(value)
);

describe('icon-only Button accessibility audit', () => {
  it('ensures icon-only Button usages include an accessible label', () => {
    const sourceFiles: string[] = [];
    ROOT_DIRS.forEach((dir) => collectSourceFiles(path.join(process.cwd(), dir), sourceFiles));

    const unlabeledButtons: string[] = [];
    const buttonPattern = /<Button\b([^>]*)>([\s\S]*?)<\/Button>/g;

    sourceFiles.forEach((filePath) => {
      const source = readFileSync(filePath, 'utf-8');
      let match = buttonPattern.exec(source);
      while (match) {
        const attrs = match[1];
        const content = match[2].trim();

        const hasLabelAttribute = /\baria-label\s*=/.test(attrs) || /\baria-labelledby\s*=/.test(attrs);
        const hasVisibleText = stripJsxToText(content).length > 0 || hasStringLiteralText(content);
        const hasIconMarkup = /<[A-Z][A-Za-z0-9]*(\s|\/>)/.test(content);
        const isIconOnly = hasIconMarkup && !hasVisibleText;

        if (isIconOnly && !hasLabelAttribute) {
          const line = source.slice(0, match.index).split('\n').length;
          unlabeledButtons.push(`${path.relative(process.cwd(), filePath)}:${line}`);
        }

        match = buttonPattern.exec(source);
      }
    });

    expect(unlabeledButtons, `Unlabeled icon-only buttons found:\n${unlabeledButtons.join('\n')}`).toEqual([]);
  });
});
