export type MarkdownInline =
  | { type: "text"; text: string }
  | { type: "strong"; text: string }
  | { type: "em"; text: string }
  | { type: "code"; text: string }
  | { type: "link"; text: string; href: string };

export type MarkdownBlock =
  | { type: "heading"; level: 1 | 2 | 3; content: MarkdownInline[] }
  | { type: "paragraph"; content: MarkdownInline[] }
  | { type: "unordered-list"; items: MarkdownInline[][] }
  | { type: "ordered-list"; items: MarkdownInline[][] };

function isSafeHref(value: string): boolean {
  return /^(https?:\/\/|mailto:)/i.test(value);
}

export function parseInlineMarkdown(value: string): MarkdownInline[] {
  const tokens: MarkdownInline[] = [];
  const pattern = /(\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^\s)]+(?:\([^)]*\))?)\)|\*([^*]+)\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(value)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ type: "text", text: value.slice(lastIndex, match.index) });
    }

    if (match[2]) {
      tokens.push({ type: "strong", text: match[2] });
    } else if (match[3]) {
      tokens.push({ type: "code", text: match[3] });
    } else if (match[4] && match[5] && isSafeHref(match[5])) {
      tokens.push({ type: "link", text: match[4], href: match[5] });
    } else if (match[4]) {
      tokens.push({ type: "text", text: match[4] });
      if (value[pattern.lastIndex] === ")") {
        pattern.lastIndex += 1;
      }
    } else if (match[6]) {
      tokens.push({ type: "em", text: match[6] });
    }

    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < value.length) {
    tokens.push({ type: "text", text: value.slice(lastIndex) });
  }

  return tokens.length > 0 ? tokens : [{ type: "text", text: value }];
}

export function parseMarkdownBlocks(markdown: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  let paragraph: string[] = [];
  let unorderedItems: MarkdownInline[][] = [];
  let orderedItems: MarkdownInline[][] = [];

  function flushParagraph() {
    if (paragraph.length > 0) {
      blocks.push({ type: "paragraph", content: parseInlineMarkdown(paragraph.join(" ")) });
      paragraph = [];
    }
  }

  function flushLists() {
    if (unorderedItems.length > 0) {
      blocks.push({ type: "unordered-list", items: unorderedItems });
      unorderedItems = [];
    }
    if (orderedItems.length > 0) {
      blocks.push({ type: "ordered-list", items: orderedItems });
      orderedItems = [];
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (!line) {
      flushParagraph();
      flushLists();
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      flushLists();
      blocks.push({
        type: "heading",
        level: heading[1].length as 1 | 2 | 3,
        content: parseInlineMarkdown(heading[2]),
      });
      continue;
    }

    const unordered = /^[-*]\s+(.+)$/.exec(line);
    if (unordered) {
      flushParagraph();
      unorderedItems.push(parseInlineMarkdown(unordered[1]));
      continue;
    }

    const ordered = /^\d+[.)]\s+(.+)$/.exec(line);
    if (ordered) {
      flushParagraph();
      orderedItems.push(parseInlineMarkdown(ordered[1]));
      continue;
    }

    flushLists();
    paragraph.push(line);
  }

  flushParagraph();
  flushLists();

  return blocks;
}
