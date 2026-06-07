import { parseMarkdownBlocks, type MarkdownInline } from "../lib/markdown";

interface MarkdownContentProps {
  markdown: string;
  emptyText?: string;
}

function inlineNodes(tokens: MarkdownInline[]) {
  return tokens.map((token, index) => {
    if (token.type === "strong") return <strong key={index}>{token.text}</strong>;
    if (token.type === "em") return <em key={index}>{token.text}</em>;
    if (token.type === "code") return <code key={index}>{token.text}</code>;
    if (token.type === "link") {
      return (
        <a key={index} href={token.href} rel="noreferrer" target="_blank">
          {token.text}
        </a>
      );
    }
    return token.text;
  });
}

export default function MarkdownContent({ markdown, emptyText = "Nothing here yet." }: MarkdownContentProps) {
  const blocks = parseMarkdownBlocks(markdown);

  if (blocks.length === 0) {
    return <div className="markdown-content muted">{emptyText}</div>;
  }

  return (
    <div className="markdown-content">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          const Heading = `h${block.level}` as "h1" | "h2" | "h3";
          return <Heading key={index}>{inlineNodes(block.content)}</Heading>;
        }

        if (block.type === "unordered-list") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{inlineNodes(item)}</li>
              ))}
            </ul>
          );
        }

        if (block.type === "ordered-list") {
          return (
            <ol key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{inlineNodes(item)}</li>
              ))}
            </ol>
          );
        }

        return <p key={index}>{inlineNodes(block.content)}</p>;
      })}
    </div>
  );
}
