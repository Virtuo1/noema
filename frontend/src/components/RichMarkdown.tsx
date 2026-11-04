/** Established, safe Markdown pipeline for assistant responses. */

import React, {
  Children,
  isValidElement,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import { renderToString as renderKatexToString } from "katex";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import type { Element, Root, Text } from "hast";
import { visit } from "unist-util-visit";
import type { Plugin, PluggableList } from "unified";
import { getTagBadgeClasses } from "./FloatingComposer";

import "katex/dist/katex.min.css";
import "highlight.js/styles/github-dark.css";

const rehypeColorTags: Plugin<[], Root> = () => (tree) => {
  visit(tree, "text", (node, index, parent) => {
    if (index === undefined || !parent || !("children" in parent)) return;
    if (
      parent.type === "element" &&
      ["a", "code", "pre"].includes(parent.tagName)
    ) {
      return;
    }

    const pattern = /(^|\s)(#[a-zA-Z][a-zA-Z0-9_-]{1,19})\b/g;
    const replacement: (Element | Text)[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(node.value)) !== null) {
      const tagStart = match.index + match[1]!.length;
      if (tagStart > lastIndex) {
        replacement.push({
          type: "text",
          value: node.value.slice(lastIndex, tagStart),
        });
      }
      const tag = match[2]!;
      replacement.push({
        type: "element",
        tagName: "span",
        properties: { className: getTagBadgeClasses(tag).split(/\s+/) },
        children: [{ type: "text", value: tag }],
      });
      lastIndex = tagStart + tag.length;
    }

    if (replacement.length === 0) return;
    if (lastIndex < node.value.length) {
      replacement.push({ type: "text", value: node.value.slice(lastIndex) });
    }
    parent.children.splice(index, 1, ...replacement);
    return index + replacement.length;
  });
};

const rehypeStreamFade: Plugin<[], Root> = () => (tree) => {
  visit(tree, "text", (node, index, parent) => {
    if (index === undefined || !parent || !("children" in parent)) return;
    if (parent.type === "element") {
      const tag = parent.tagName.toLowerCase();
      if (["code", "pre", "a", "script", "style"].includes(tag)) {
        return;
      }
      const classes = Array.isArray(parent.properties?.className)
        ? parent.properties.className.map(String)
        : [];
      if (classes.includes("animate-token-fade") || classes.includes("katex")) {
        return;
      }
    }

    const val = node.value;
    if (!val || !val.trim()) return;

    // Split text into tokens (words/punctuation and whitespace)
    const tokens = val.match(/\S+\s*|\s+/g);
    if (!tokens || tokens.length === 0) return;

    const replacement: (Element | Text)[] = tokens.map((token) => {
      if (!token.trim()) {
        return { type: "text", value: token };
      }
      return {
        type: "element",
        tagName: "span",
        properties: {
          className: ["animate-token-fade"],
        },
        children: [{ type: "text", value: token }],
      };
    });

    parent.children.splice(index, 1, ...replacement);
    return index + replacement.length;
  });
};

const rehypeMath: [
  typeof rehypeKatex,
  { throwOnError: boolean; strict: boolean; minRuleThickness: number },
] = [
  rehypeKatex,
  {
    throwOnError: false,
    strict: false,
    minRuleThickness: 0.05,
  },
];

const rehypeHighlightConfig: [
  typeof rehypeHighlight,
  { detect: boolean; ignoreMissing: boolean },
] = [rehypeHighlight, { detect: false, ignoreMissing: true }];

function getPlainText(node: React.ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(getPlainText).join("");
  if (isValidElement<{ children?: React.ReactNode }>(node)) {
    return getPlainText(node.props.children);
  }
  return "";
}

const CodeBlock: React.FC<{
  language: string;
  code: string;
  children: React.ReactNode;
}> = ({ language, code, children }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    void navigator.clipboard?.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="my-3.5 overflow-hidden rounded-2xl border border-white/[0.08] bg-zinc-950/95 shadow-lg animate-fade-in">
      <div className="flex items-center justify-between border-b border-white/[0.06] bg-white/[0.03] px-4 py-2 text-[11px] text-zinc-400">
        <span className="font-mono lowercase text-zinc-300">
          {language || "code"}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="rounded bg-white/[0.04] px-2 py-0.5 text-zinc-400 transition-colors hover:bg-white/[0.08] hover:text-white"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-[13px] leading-relaxed bg-transparent">
        <code className="hljs font-mono text-zinc-200 !bg-transparent">{children || code}</code>
      </pre>
    </div>
  );
};

const markdownComponents: Components = {
  h1: ({ children, ...props }) => (
    <h1
      className="mb-2 mt-5 text-xl font-semibold tracking-tight text-white animate-fade-in"
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2
      className="mb-2 mt-4 text-lg font-semibold tracking-tight text-white animate-fade-in"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3
      className="mb-1.5 mt-3.5 text-base font-semibold text-zinc-100 animate-fade-in"
      {...props}
    >
      {children}
    </h3>
  ),
  h4: ({ children, ...props }) => (
    <h4
      className="mb-1 mt-3 text-sm font-semibold text-zinc-200 animate-fade-in"
      {...props}
    >
      {children}
    </h4>
  ),
  p: ({ children, ...props }) => (
    <p className="my-2.5 leading-relaxed text-zinc-200" {...props}>
      {children}
    </p>
  ),
  a: ({ children, ...props }) => (
    <a
      className="text-white underline decoration-white/30 transition-colors hover:decoration-white"
      target="_blank"
      rel="noreferrer"
      {...props}
    >
      {children}
    </a>
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="my-3 border-l-2 border-white/20 pl-4 text-zinc-300 animate-fade-in"
      {...props}
    >
      {children}
    </blockquote>
  ),
  ul: ({ children, ...props }) => (
    <ul
      className="my-2.5 list-disc space-y-1 pl-6 text-zinc-200 animate-fade-in"
      {...props}
    >
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol
      className="my-2.5 list-decimal space-y-1 pl-6 text-zinc-200 animate-fade-in"
      {...props}
    >
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="pl-1 leading-relaxed marker:text-zinc-500" {...props}>
      {children}
    </li>
  ),
  hr: () => <hr className="my-4 border-t border-white/[0.08]" />,
  table: ({ children, ...props }) => (
    <div className="my-3 overflow-x-auto rounded-xl border border-white/[0.08] animate-fade-in">
      <table className="w-full border-collapse text-left text-sm" {...props}>
        {children}
      </table>
    </div>
  ),
  th: ({ children, ...props }) => (
    <th
      className="border-b border-white/[0.12] bg-white/[0.05] px-3 py-2 font-semibold text-white"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td
      className="border-b border-white/[0.06] px-3 py-2 align-top text-zinc-300"
      {...props}
    >
      {children}
    </td>
  ),
  code: ({ children, className, ...props }) => {
    const block = Boolean(className?.includes("language-"));
    return (
      <code
        className={
          block
            ? `${className ?? ""} font-mono text-[13px]`
            : "rounded-md border border-white/[0.08] bg-white/[0.08] px-1.5 py-0.5 font-mono text-[13px] text-zinc-100"
        }
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => {
    const codeElement = Children.toArray(children)[0];
    if (
      !isValidElement<{ className?: string; children?: React.ReactNode }>(
        codeElement,
      )
    ) {
      return (
        <pre className="my-3 overflow-x-auto rounded-xl bg-zinc-950 p-4 animate-fade-in">
          {children}
        </pre>
      );
    }
    const language =
      codeElement.props.className?.match(/language-([\w-]+)/)?.[1] ?? "";
    const code = getPlainText(codeElement.props.children).replace(/\n$/, "");
    return (
      <CodeBlock language={language} code={code}>
        {codeElement.props.children}
      </CodeBlock>
    );
  },
};

interface RichMarkdownProps {
  content: string;
  isStreaming?: boolean;
}

export const RichMarkdown: React.FC<RichMarkdownProps> = ({
  content,
  isStreaming = false,
}) => {
  const [renderedContent, setRenderedContent] = useState(content);
  const pendingContentRef = useRef(content);
  const rafIdRef = useRef<number | null>(null);

  useEffect(() => {
    pendingContentRef.current = content;
    if (!isStreaming) {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
      setRenderedContent(content);
      return;
    }
    if (rafIdRef.current === null) {
      rafIdRef.current = requestAnimationFrame(() => {
        rafIdRef.current = null;
        setRenderedContent(pendingContentRef.current);
      });
    }
  }, [content, isStreaming]);

  useEffect(
    () => () => {
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
      }
    },
    [],
  );

  const rehypePlugins = useMemo(() => {
    const plugins: PluggableList = [
      rehypeColorTags,
      rehypeMath,
      rehypeHighlightConfig,
    ];
    if (isStreaming) {
      plugins.push(rehypeStreamFade);
    }
    return plugins;
  }, [isStreaming]);

  return (
    <div className="noema-markdown min-w-0 break-words">
      <ReactMarkdown
        skipHtml
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={rehypePlugins}
        components={markdownComponents}
      >
        {renderedContent}
      </ReactMarkdown>
    </div>
  );
};

/** Backwards-compatible helper; new response rendering uses remark-math and KaTeX. */
export function renderLatexMath(raw: string): React.ReactNode {
  return (
    <span
      dangerouslySetInnerHTML={{
        __html: renderKatexToString(raw, {
          throwOnError: false,
          output: "htmlAndMathml",
        }),
      }}
    />
  );
}
