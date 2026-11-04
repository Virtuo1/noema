/**
 * Rich Markdown, Code Block, and LaTeX Math Renderer for Noema.
 * Supports:
 * - Headings (#, ##, ###, ####)
 * - Fenced code blocks (```lang ... ```) with language badge & copy button (works while streaming)
 * - Display math ($$ ... $$ and \[ ... \]) & Inline math ($ ... $ and \( ... \)) with LaTeX formatting
 * - Bullet & numbered lists, blockquotes (>), GFM tables, and horizontal rules (---)
 * - Inline bold (**), italic (*), bold-italic (***), inline code (`), links, and colored #tags
 * - Smooth per-word fade-in (.animate-token-fade) when `isStreaming` is true
 */

import React, { useState } from "react";
import { getTagBadgeClasses } from "./FloatingComposer";

const LATEX_SYMBOLS: Record<string, string> = {
  "\\alpha": "α",
  "\\beta": "β",
  "\\gamma": "γ",
  "\\delta": "δ",
  "\\epsilon": "ϵ",
  "\\varepsilon": "ε",
  "\\zeta": "ζ",
  "\\eta": "η",
  "\\theta": "θ",
  "\\vartheta": "ϑ",
  "\\iota": "ι",
  "\\kappa": "κ",
  "\\lambda": "λ",
  "\\mu": "μ",
  "\\nu": "ν",
  "\\xi": "ξ",
  "\\pi": "π",
  "\\rho": "ρ",
  "\\sigma": "σ",
  "\\tau": "τ",
  "\\upsilon": "υ",
  "\\phi": "ϕ",
  "\\varphi": "φ",
  "\\chi": "χ",
  "\\psi": "ψ",
  "\\omega": "ω",
  "\\Gamma": "Γ",
  "\\Delta": "Δ",
  "\\Theta": "Θ",
  "\\Lambda": "Λ",
  "\\Xi": "Ξ",
  "\\Pi": "Π",
  "\\Sigma": "Σ",
  "\\Phi": "Φ",
  "\\Psi": "Ψ",
  "\\Omega": "Ω",
  "\\nabla": "∇",
  "\\partial": "∂",
  "\\infty": "∞",
  "\\approx": "≈",
  "\\neq": "≠",
  "\\ne": "≠",
  "\\leq": "≤",
  "\\le": "≤",
  "\\geq": "≥",
  "\\ge": "≥",
  "\\pm": "±",
  "\\mp": "∓",
  "\\times": "×",
  "\\cdot": "·",
  "\\div": "÷",
  "\\sum": "∑",
  "\\prod": "∏",
  "\\int": "∫",
  "\\oint": "∮",
  "\\to": "→",
  "\\rightarrow": "→",
  "\\leftarrow": "←",
  "\\Rightarrow": "⇒",
  "\\Leftarrow": "⇐",
  "\\leftrightarrow": "↔",
  "\\Leftrightarrow": "⇔",
  "\\iff": "⟺",
  "\\in": "∈",
  "\\notin": "∉",
  "\\subset": "⊂",
  "\\subseteq": "⊆",
  "\\cup": "∪",
  "\\cap": "∩",
  "\\forall": "∀",
  "\\exists": "∃",
  "\\emptyset": "∅",
  "\\propto": "∝",
  "\\equiv": "≡",
  "\\sim": "∼",
  "\\perp": "⊥",
  "\\parallel": "∥",
  "\\dots": "…",
  "\\ldots": "…",
  "\\cdots": "⋯",
  "\\mathbb{R}": "ℝ",
  "\\mathbb{N}": "ℕ",
  "\\mathbb{Z}": "ℤ",
  "\\mathbb{Q}": "ℚ",
  "\\mathbb{C}": "ℂ",
  "\\mathbb{E}": "𝔼",
  "\\mathcal{L}": "ℒ",
  "\\mathcal{N}": "𝒩",
  "\\mathcal{O}": "𝒪",
};

/** Render LaTeX math string into clean typographic React nodes (fractions, sub/superscripts, Greek, operators). */
export function renderLatexMath(raw: string): React.ReactNode {
  let expr = raw.trim();

  // Strip sizing helpers
  expr = expr
    .replace(/\\left\s*/g, "")
    .replace(/\\right\s*/g, "")
    .replace(/\\,/g, " ")
    .replace(/\\;/g, " ")
    .replace(/\\quad/g, "  ")
    .replace(/\\qquad/g, "    ");

  // Replace \text{...} and \mathrm{...} and \mathbf{...}
  expr = expr.replace(
    /\\(?:text|mathrm|mathbf|operatorname)\{([^{}]*)\}/g,
    "$1",
  );

  // Replace \hat{x}, \bar{x}, \vec{x}
  expr = expr
    .replace(/\\hat\{([^{}])\}/g, "$1\u0302")
    .replace(/\\bar\{([^{}])\}/g, "$1\u0304")
    .replace(/\\vec\{([^{}])\}/g, "$1\u20d7");

  // Replace \sqrt{...}
  expr = expr.replace(/\\sqrt\{([^{}]*)\}/g, "√($1)");

  // Replace known symbols (longest first so \varepsilon beats \epsilon, \mathbb{R} works, etc.)
  const sortedKeys = Object.keys(LATEX_SYMBOLS).sort(
    (a, b) => b.length - a.length,
  );
  for (const k of sortedKeys) {
    expr = expr.split(k).join(LATEX_SYMBOLS[k]);
  }

  // Handle \frac{num}{den} iteratively (up to 3 nesting levels)
  for (let pass = 0; pass < 3; pass++) {
    expr = expr.replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, "($1) / ($2)");
  }

  // Parse superscripts (^{...} or ^x) and subscripts (_{...} or _x) into React <sup> and <sub>
  const parts: React.ReactNode[] = [];
  const tokenRegex =
    /(\^\{([^{}]*)\}|\^([a-zA-Z0-9+-])|_\{([^{}]*)\}|_([a-zA-Z0-9+-]))/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let idx = 0;

  while ((match = tokenRegex.exec(expr)) !== null) {
    if (match.index > lastIndex) {
      parts.push(expr.slice(lastIndex, match.index));
    }
    const supGroup = match[2] ?? match[3];
    const subGroup = match[4] ?? match[5];
    if (supGroup !== undefined) {
      parts.push(
        <sup key={`sup-${idx++}`} className="text-[0.78em] leading-none">
          {supGroup}
        </sup>,
      );
    } else if (subGroup !== undefined) {
      parts.push(
        <sub key={`sub-${idx++}`} className="text-[0.78em] leading-none">
          {subGroup}
        </sub>,
      );
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < expr.length) {
    parts.push(expr.slice(lastIndex));
  }

  return parts;
}

const CodeBlock: React.FC<{ language: string; code: string }> = ({
  language,
  code,
}) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    void navigator.clipboard?.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="my-3.5 rounded-2xl bg-zinc-950/95 border border-white/[0.08] overflow-hidden shadow-lg">
      <div className="px-4 py-2 bg-white/[0.03] border-b border-white/[0.06] flex items-center justify-between text-[11px] text-zinc-400">
        <span className="font-mono lowercase text-zinc-300">
          {language || "code"}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="text-zinc-400 hover:text-white transition-colors px-2 py-0.5 rounded bg-white/[0.04] hover:bg-white/[0.08]"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="p-4 text-[13px] leading-relaxed font-mono text-zinc-200 overflow-x-auto">
        <code>{code}</code>
      </pre>
    </div>
  );
};

interface RichMarkdownProps {
  content: string;
  isStreaming?: boolean;
}

export const RichMarkdown: React.FC<RichMarkdownProps> = ({
  content,
  isStreaming = false,
}) => {
  const renderPlainTextSegment = (
    text: string,
    keyPrefix: string,
  ): React.ReactNode => {
    if (!isStreaming) return text;
    const words = text.match(/\S+\s*|\s+/g) ?? [text];
    return words.map((word, wIdx) => (
      <span key={`${keyPrefix}-w-${wIdx}`} className="animate-token-fade">
        {word}
      </span>
    ));
  };

  /** Parse inline markdown: `code`, $math$, \(math\), **bold**, *italic*, [link](url), and #tags */
  const renderInline = (text: string, keyPrefix: string): React.ReactNode[] => {
    const nodes: React.ReactNode[] = [];
    const inlinePattern =
      /(`[^`]+`|\$\$[^$]+\$\$|\$[^$\n]+\$|\\\([\s\S]+?\\\)|\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*(?!\s)[^*\n]+(?<!\s)\*|\[[^\]]+\]\([^)]+\)|(?:^|\s)#[a-zA-Z]{2,20}\b)/g;

    let lastIdx = 0;
    let match: RegExpExecArray | null;
    let tokenIdx = 0;

    while ((match = inlinePattern.exec(text)) !== null) {
      if (match.index > lastIdx) {
        nodes.push(
          renderPlainTextSegment(
            text.slice(lastIdx, match.index),
            `${keyPrefix}-p-${tokenIdx++}`,
          ),
        );
      }

      const token = match[0];
      const tKey = `${keyPrefix}-i-${tokenIdx++}`;

      if (token.startsWith("`") && token.endsWith("`")) {
        nodes.push(
          <code
            key={tKey}
            className="font-mono text-[13px] bg-white/[0.08] border border-white/[0.08] px-1.5 py-0.5 rounded-md text-zinc-100"
          >
            {token.slice(1, -1)}
          </code>,
        );
      } else if (
        (token.startsWith("$$") && token.endsWith("$$")) ||
        (token.startsWith("$") && token.endsWith("$")) ||
        (token.startsWith("\\(") && token.endsWith("\\)"))
      ) {
        const innerMath = token.startsWith("$$")
          ? token.slice(2, -2)
          : token.startsWith("\\(")
            ? token.slice(2, -2)
            : token.slice(1, -1);
        nodes.push(
          <span
            key={tKey}
            className="font-serif italic text-zinc-100 bg-white/[0.04] px-1.5 py-0.5 rounded"
          >
            {renderLatexMath(innerMath)}
          </span>,
        );
      } else if (token.startsWith("***") && token.endsWith("***")) {
        nodes.push(
          <strong key={tKey} className="font-semibold italic text-white">
            {renderPlainTextSegment(token.slice(3, -3), tKey)}
          </strong>,
        );
      } else if (token.startsWith("**") && token.endsWith("**")) {
        nodes.push(
          <strong key={tKey} className="font-semibold text-white">
            {renderPlainTextSegment(token.slice(2, -2), tKey)}
          </strong>,
        );
      } else if (token.startsWith("*") && token.endsWith("*")) {
        nodes.push(
          <em key={tKey} className="italic text-zinc-100">
            {renderPlainTextSegment(token.slice(1, -1), tKey)}
          </em>,
        );
      } else if (token.startsWith("[") && token.includes("](")) {
        const splitIdx = token.indexOf("](");
        const label = token.slice(1, splitIdx);
        const url = token.slice(splitIdx + 2, -1);
        nodes.push(
          <a
            key={tKey}
            href={url}
            target="_blank"
            rel="noreferrer"
            className="text-white underline decoration-white/30 hover:decoration-white transition-colors"
          >
            {label}
          </a>,
        );
      } else if (token.trim().startsWith("#")) {
        const leadingSpace = token.startsWith(" ") ? " " : "";
        const tagText = token.trim();
        nodes.push(
          <React.Fragment key={tKey}>
            {leadingSpace}
            <span
              className={`inline-flex items-center text-[11px] font-mono px-1.5 py-0.5 rounded border ${getTagBadgeClasses(
                tagText,
              )}`}
            >
              {tagText}
            </span>
          </React.Fragment>,
        );
      } else {
        nodes.push(renderPlainTextSegment(token, tKey));
      }

      lastIdx = match.index + token.length;
    }

    if (lastIdx < text.length) {
      nodes.push(
        renderPlainTextSegment(
          text.slice(lastIdx),
          `${keyPrefix}-tail-${tokenIdx}`,
        ),
      );
    }

    return nodes;
  };

  // First split content into fenced code blocks (```...```), display math blocks ($$...$$ or \[...\]), and markdown prose
  const blocks: React.ReactNode[] = [];
  const blockRegex =
    /(```([a-zA-Z0-9_-]*)\n([\s\S]*?)(?:```|$)|\$\$([\s\S]*?)(?:\$\$|$)|\\\[([\s\S]*?)(?:\\\]|$))/g;

  let lastBlockIdx = 0;
  let blockMatch: RegExpExecArray | null;
  let bCounter = 0;

  const renderProseChunk = (prose: string, chunkKey: string) => {
    const lines = prose.split("\n");
    const elements: React.ReactNode[] = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i] ?? "";
      const trimmed = line.trim();

      if (!trimmed) {
        i++;
        continue;
      }

      // Horizontal Rule
      if (/^(?:---|\*\*\*|___)\s*$/.test(trimmed)) {
        elements.push(
          <hr
            key={`${chunkKey}-hr-${i}`}
            className="my-4 border-t border-white/[0.08]"
          />,
        );
        i++;
        continue;
      }

      // Headings (# to ####)
      const headingMatch = /^(#{1,4})\s+(.+)$/.exec(trimmed);
      if (headingMatch) {
        const level = headingMatch[1]!.length;
        const headingText = headingMatch[2]!;
        const hKey = `${chunkKey}-h-${i}`;
        if (level === 1) {
          elements.push(
            <h1
              key={hKey}
              className="mt-5 mb-2 text-xl font-semibold text-white tracking-tight"
            >
              {renderInline(headingText, hKey)}
            </h1>,
          );
        } else if (level === 2) {
          elements.push(
            <h2
              key={hKey}
              className="mt-4 mb-2 text-lg font-semibold text-white tracking-tight"
            >
              {renderInline(headingText, hKey)}
            </h2>,
          );
        } else if (level === 3) {
          elements.push(
            <h3
              key={hKey}
              className="mt-3.5 mb-1.5 text-base font-semibold text-zinc-100"
            >
              {renderInline(headingText, hKey)}
            </h3>,
          );
        } else {
          elements.push(
            <h4
              key={hKey}
              className="mt-3 mb-1 text-sm font-semibold text-zinc-200"
            >
              {renderInline(headingText, hKey)}
            </h4>,
          );
        }
        i++;
        continue;
      }

      // Blockquote (>)
      if (trimmed.startsWith(">")) {
        const quoteLines: string[] = [];
        while (i < lines.length && (lines[i] ?? "").trim().startsWith(">")) {
          quoteLines.push((lines[i] ?? "").trim().replace(/^>\s?/, ""));
          i++;
        }
        const qKey = `${chunkKey}-q-${i}`;
        elements.push(
          <blockquote
            key={qKey}
            className="my-3 border-l-2 border-white/20 pl-4 italic text-zinc-300 space-y-1"
          >
            {quoteLines.map((ql, qIdx) => (
              <p key={`${qKey}-${qIdx}`}>
                {renderInline(ql, `${qKey}-${qIdx}`)}
              </p>
            ))}
          </blockquote>,
        );
        continue;
      }

      // Unordered List (- or * or •)
      if (/^[-*•]\s+/.test(trimmed)) {
        const items: string[] = [];
        while (i < lines.length && /^[-*•]\s+/.test((lines[i] ?? "").trim())) {
          items.push((lines[i] ?? "").trim().replace(/^[-*•]\s+/, ""));
          i++;
        }
        const ulKey = `${chunkKey}-ul-${i}`;
        elements.push(
          <ul
            key={ulKey}
            className="my-2.5 pl-5 list-disc space-y-1.5 text-zinc-200 marker:text-zinc-500"
          >
            {items.map((item, idx) => (
              <li key={`${ulKey}-${idx}`} className="leading-relaxed">
                {renderInline(item, `${ulKey}-${idx}`)}
              </li>
            ))}
          </ul>,
        );
        continue;
      }

      // Ordered List (1. 2. ...)
      if (/^\d+\.\s+/.test(trimmed)) {
        const items: string[] = [];
        while (i < lines.length && /^\d+\.\s+/.test((lines[i] ?? "").trim())) {
          items.push((lines[i] ?? "").trim().replace(/^\d+\.\s+/, ""));
          i++;
        }
        const olKey = `${chunkKey}-ol-${i}`;
        elements.push(
          <ol
            key={olKey}
            className="my-2.5 pl-5 list-decimal space-y-1.5 text-zinc-200 marker:text-zinc-400"
          >
            {items.map((item, idx) => (
              <li key={`${olKey}-${idx}`} className="leading-relaxed">
                {renderInline(item, `${olKey}-${idx}`)}
              </li>
            ))}
          </ol>,
        );
        continue;
      }

      // GFM Table (| ... |)
      if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
        const tableLines: string[] = [];
        while (i < lines.length && (lines[i] ?? "").trim().startsWith("|")) {
          tableLines.push((lines[i] ?? "").trim());
          i++;
        }
        const rows = tableLines
          .filter((tl) => !/^\|[\s:-]+\|$/.test(tl.replace(/\|/g, "|")))
          .filter((tl) => !/^[\s|:-]+$/.test(tl))
          .map((tl) =>
            tl
              .slice(1, -1)
              .split("|")
              .map((c) => c.trim()),
          );
        if (rows.length > 0) {
          const tKey = `${chunkKey}-tbl-${i}`;
          const header = rows[0]!;
          const body = rows.slice(1);
          elements.push(
            <div
              key={tKey}
              className="my-3.5 overflow-x-auto rounded-2xl border border-white/[0.08]"
            >
              <table className="w-full text-left text-xs text-zinc-200">
                <thead className="bg-white/[0.04] border-b border-white/[0.08] text-zinc-300">
                  <tr>
                    {header.map((cell, cIdx) => (
                      <th key={cIdx} className="px-3.5 py-2 font-semibold">
                        {renderInline(cell, `${tKey}-th-${cIdx}`)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.05]">
                  {body.map((r, rIdx) => (
                    <tr key={rIdx}>
                      {r.map((cell, cIdx) => (
                        <td key={cIdx} className="px-3.5 py-2">
                          {renderInline(cell, `${tKey}-td-${rIdx}-${cIdx}`)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>,
          );
          continue;
        }
      }

      // Regular paragraph: collect consecutive non-special lines
      const paraLines: string[] = [];
      while (i < lines.length) {
        const cur = (lines[i] ?? "").trim();
        if (
          !cur ||
          /^(#{1,4})\s+/.test(cur) ||
          cur.startsWith(">") ||
          /^[-*•]\s+/.test(cur) ||
          /^\d+\.\s+/.test(cur) ||
          (cur.startsWith("|") && cur.endsWith("|")) ||
          /^(?:---|\*\*\*|___)\s*$/.test(cur)
        ) {
          break;
        }
        paraLines.push(lines[i] ?? "");
        i++;
      }
      const pKey = `${chunkKey}-p-${i}`;
      elements.push(
        <p key={pKey} className="my-2.5 leading-relaxed text-zinc-200">
          {renderInline(paraLines.join("\n"), pKey)}
        </p>,
      );
    }

    return elements;
  };

  while ((blockMatch = blockRegex.exec(content)) !== null) {
    if (blockMatch.index > lastBlockIdx) {
      const prose = content.slice(lastBlockIdx, blockMatch.index);
      blocks.push(...renderProseChunk(prose, `b-${bCounter++}`));
    }

    const fullMatch = blockMatch[0];
    if (fullMatch.startsWith("```")) {
      const lang = blockMatch[2] ?? "";
      const code = (blockMatch[3] ?? "").replace(/\n$/, "");
      blocks.push(
        <CodeBlock key={`code-${bCounter++}`} language={lang} code={code} />,
      );
    } else {
      const mathContent = blockMatch[4] ?? blockMatch[5] ?? "";
      blocks.push(
        <div
          key={`math-${bCounter++}`}
          className="my-3.5 py-3 px-4 rounded-2xl bg-white/[0.03] border border-white/[0.06] text-center font-serif italic text-base text-zinc-100 overflow-x-auto"
        >
          {renderLatexMath(mathContent)}
        </div>,
      );
    }

    lastBlockIdx = blockMatch.index + fullMatch.length;
  }

  if (lastBlockIdx < content.length) {
    blocks.push(
      ...renderProseChunk(content.slice(lastBlockIdx), `b-${bCounter++}`),
    );
  }

  return <div className="space-y-1">{blocks}</div>;
};
