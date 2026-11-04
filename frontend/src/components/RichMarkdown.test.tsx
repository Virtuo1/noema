import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RichMarkdown, renderLatexMath } from "./RichMarkdown";

describe("RichMarkdown Component", () => {
  it("renders headings properly as semantic heading elements", () => {
    const markdown = "# Heading 1\n## Heading 2\n### Heading 3";
    render(<RichMarkdown content={markdown} />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Heading 1" }),
    ).toBeDefined();
    expect(
      screen.getByRole("heading", { level: 2, name: "Heading 2" }),
    ).toBeDefined();
    expect(
      screen.getByRole("heading", { level: 3, name: "Heading 3" }),
    ).toBeDefined();
  });

  it("renders fenced code blocks with language badge and copy button", () => {
    const markdown =
      "```python\ndef backprop(gradient):\n    return gradient * 0.1\n```";
    render(<RichMarkdown content={markdown} />);

    expect(screen.getByText("python")).toBeDefined();
    expect(screen.getByText("Copy")).toBeDefined();
    expect(screen.getByText("backprop")).toBeDefined();
  });

  it("renders display math and inline math with LaTeX Greek and operator symbols", () => {
    const markdown =
      "The loss function is:\n\n$$\n\\mathcal{L} = \\frac{1}{2} (y - \\hat{y})^2\n$$\n\nwhere $\\alpha \\in \\mathbb{R}$.";
    const { container } = render(<RichMarkdown content={markdown} />);

    expect(container.querySelector(".katex")).not.toBeNull();
    expect(container.querySelector(".katex-display")).not.toBeNull();
    expect(container.textContent).toContain("α");
    expect(container.textContent).toContain("∈");
  });

  it("renders tables and lists correctly", () => {
    const markdown =
      "- Item A\n- Item B\n\n| Concept | Layer |\n|---|---|\n| Backprop | Neural |\n| Chain rule | Calculus |";
    render(<RichMarkdown content={markdown} />);

    expect(screen.getByText("Item A")).toBeDefined();
    expect(screen.getByText("Item B")).toBeDefined();
    expect(screen.getByText("Backprop")).toBeDefined();
    expect(screen.getByText("Chain rule")).toBeDefined();
  });

  it("renderLatexMath handles fractions, sub/superscripts, and symbols", () => {
    const node = renderLatexMath("\\sum_{i=1}^{N} x_i^2");
    const { container } = render(<div>{node}</div>);

    expect(container.textContent).toContain("∑");
    expect(container.querySelector("sup")).toBeDefined();
    expect(container.querySelector("sub")).toBeDefined();
  });

  it("renders fractions with square roots in math notation cleanly", () => {
    const markdown =
      "Gaussian PDF is:\n\n$$\np(x) = \\frac{1}{\\sqrt{2\\pi\\sigma^2}} \\exp\\left(-\\frac{(x-\\mu)^2}{2\\sigma^2}\\right)\n$$";
    const { container } = render(<RichMarkdown content={markdown} />);

    expect(container.querySelector(".katex")).not.toBeNull();
    expect(container.querySelector(".mfrac")).not.toBeNull();
    expect(container.querySelector(".sqrt")).not.toBeNull();
    expect(container.querySelector(".frac-line")).not.toBeNull();
  });

  it("applies animate-token-fade spans to words when isStreaming is true", () => {
    const markdown = "Backpropagation computes gradients #aha";
    const { container } = render(
      <RichMarkdown content={markdown} isStreaming={true} />,
    );

    const tokenSpans = container.querySelectorAll(".animate-token-fade");
    expect(tokenSpans.length).toBeGreaterThan(0);
    expect(container.textContent).toContain("Backpropagation");
    expect(container.textContent).toContain("#aha");
  });
});
