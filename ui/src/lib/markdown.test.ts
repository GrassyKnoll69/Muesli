import { describe, expect, it } from "vitest";
import { parseInlineMarkdown, parseMarkdownBlocks } from "./markdown";

describe("parseMarkdownBlocks", () => {
  it("parses headings, paragraphs, and lists", () => {
    const blocks = parseMarkdownBlocks("## Summary\nDiscussed follow-up.\n\n- Call Alex\n- Send recap");

    expect(blocks).toEqual([
      { type: "heading", level: 2, content: [{ type: "text", text: "Summary" }] },
      { type: "paragraph", content: [{ type: "text", text: "Discussed follow-up." }] },
      {
        type: "unordered-list",
        items: [
          [{ type: "text", text: "Call Alex" }],
          [{ type: "text", text: "Send recap" }],
        ],
      },
    ]);
  });

  it("parses ordered lists without mixing them into paragraphs", () => {
    const blocks = parseMarkdownBlocks("1. Review notes\n2. Share action items");

    expect(blocks).toEqual([
      {
        type: "ordered-list",
        items: [
          [{ type: "text", text: "Review notes" }],
          [{ type: "text", text: "Share action items" }],
        ],
      },
    ]);
  });
});

describe("parseInlineMarkdown", () => {
  it("parses basic inline emphasis and code", () => {
    expect(parseInlineMarkdown("Use **bold**, *italics*, and `code`.")).toEqual([
      { type: "text", text: "Use " },
      { type: "strong", text: "bold" },
      { type: "text", text: ", " },
      { type: "em", text: "italics" },
      { type: "text", text: ", and " },
      { type: "code", text: "code" },
      { type: "text", text: "." },
    ]);
  });

  it("keeps unsafe links as text", () => {
    expect(parseInlineMarkdown("[bad](javascript:alert(1))")).toEqual([
      { type: "text", text: "bad" },
    ]);
  });
});
