import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TelegramHtml } from "./TelegramHtml";

function html(source: string) {
  const { container } = render(<TelegramHtml html={source} />);
  return container;
}

describe("TelegramHtml", () => {
  it("renders the supported tags as real elements", () => {
    const container = html("<b>مهم</b> <i>کج</i> <code>NN-1234</code>");
    expect(container.querySelector("b")).toHaveTextContent("مهم");
    expect(container.querySelector("i")).toHaveTextContent("کج");
    expect(container.querySelector("code")).toHaveTextContent("NN-1234");
  });

  it("never injects raw markup from an unknown tag", () => {
    const container = html('<b>ok</b><img src=x onerror="alert(1)">');
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img");
  });

  it("drops javascript links but keeps the label", () => {
    const container = html('<a href="javascript:alert(1)">کلیک</a>');
    const link = container.querySelector("a");
    expect(link).not.toBeNull();
    expect(link?.getAttribute("href")).toBeNull();
    expect(link).toHaveTextContent("کلیک");
  });

  it("keeps safe links and opens them in a new tab", () => {
    const container = html('<a href="https://netnova.ir">سایت</a>');
    const link = container.querySelector("a");
    expect(link?.getAttribute("href")).toBe("https://netnova.ir");
    expect(link?.getAttribute("rel")).toBe("noreferrer noopener");
  });

  it("renders nested tags and unclosed tags without losing text", () => {
    const container = html("<b>متن <code>کد");
    expect(container.textContent).toBe("متن کد");
    expect(container.querySelector("b code")).not.toBeNull();
  });

  it("keeps blockquote content", () => {
    const container = html("<blockquote expandable>نقل قول</blockquote>");
    expect(container.querySelector("blockquote")).toHaveTextContent("نقل قول");
  });
});
