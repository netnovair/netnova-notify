/**
 * A deliberately tiny renderer for the Telegram HTML subset.
 *
 * The panel must never use `dangerouslySetInnerHTML` for user-provided text.
 * This parser walks the string once and builds React nodes for the tags
 * Telegram actually supports; anything else stays as visible text, so an
 * unknown or malicious tag is shown verbatim instead of executed.
 */
import { Fragment, createElement, type ReactNode } from "react";

const TAG_ALIASES = {
  b: "b",
  strong: "strong",
  i: "i",
  em: "em",
  u: "u",
  s: "s",
  del: "del",
  code: "code",
  pre: "pre",
  blockquote: "blockquote",
} as const;

type AllowedTag = (typeof TAG_ALIASES)[keyof typeof TAG_ALIASES] | "a";

const TOKEN = /<(\/?)([a-zA-Z]+)([^>]*)>|([^<]+)|(<)/g;
const SAFE_HREF = /^https?:\/\//i;

type Frame = {
  tag: AllowedTag | "root";
  nodes: ReactNode[];
  props: Record<string, unknown>;
};

function closeFrame(stack: Frame[], tag: AllowedTag | "root"): void {
  let index = stack.length - 1;
  while (index > 0 && stack[index].tag !== tag) index -= 1;
  if (index <= 0) return;
  while (stack.length - 1 > index) {
    const inner = stack.pop() as Frame;
    stack[stack.length - 1].nodes.push(
      createElement(inner.tag, inner.props, ...inner.nodes),
    );
  }
  const frame = stack.pop() as Frame;
  stack[stack.length - 1].nodes.push(createElement(frame.tag, frame.props, ...frame.nodes));
}

function renderNodes(source: string): ReactNode[] {
  const root: Frame = { tag: "root", nodes: [], props: {} };
  const stack: Frame[] = [root];
  let key = 0;
  let match: RegExpExecArray | null;

  TOKEN.lastIndex = 0;
  while ((match = TOKEN.exec(source)) !== null) {
    const [, closing, rawTag, attributes, text, stray] = match;
    if (text !== undefined) {
      stack[stack.length - 1].nodes.push(text);
      continue;
    }
    if (stray !== undefined) {
      stack[stack.length - 1].nodes.push("<");
      continue;
    }
    const name = rawTag.toLowerCase();
    if (name === "a") {
      if (closing) {
        closeFrame(stack, "a");
        continue;
      }
      const href = /href\s*=\s*"([^"]*)"/i.exec(attributes ?? "")?.[1] ?? "";
      const safe = SAFE_HREF.test(href) ? href : undefined;
      stack.push({
        tag: "a",
        nodes: [],
        props: {
          key: `a-${key++}`,
          href: safe,
          target: safe ? "_blank" : undefined,
          rel: safe ? "noreferrer noopener" : undefined,
          className: safe ? "text-[#b9a7ff] underline" : "text-muted",
        },
      });
      continue;
    }
    const tag = TAG_ALIASES[name as keyof typeof TAG_ALIASES];
    if (!tag) {
      // Unknown tag: show it as text, never interpret it.
      stack[stack.length - 1].nodes.push(match[0]);
      continue;
    }
    if (closing) {
      closeFrame(stack, tag);
      continue;
    }
    const props: Record<string, unknown> = { key: `${tag}-${key++}` };
    if (tag === "blockquote" && /expandable/.test(attributes ?? "")) {
      props.className = "border-l-2 border-accent/40 pl-3";
    }
    stack.push({ tag, nodes: [], props });
  }

  // An unclosed tag still shows its content instead of dropping everything.
  while (stack.length > 1) {
    closeFrame(stack, stack[stack.length - 1].tag);
  }
  return root.nodes;
}

/** Render the supported subset of Telegram HTML into React nodes. */
export function TelegramHtml({ html }: { html: string }) {
  return <Fragment>{renderNodes(html)}</Fragment>;
}

/** Same output without a wrapper component, for tests and previews. */
export function renderTelegramHtml(html: string): ReactNode[] {
  return renderNodes(html);
}
