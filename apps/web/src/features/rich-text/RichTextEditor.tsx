"use client";

import {
  Bold,
  Code,
  FileCode2,
  Italic,
  Link2,
  Quote,
  Strikethrough,
  Underline,
} from "lucide-react";
import { useRef, useState } from "react";

import { TelegramHtml } from "@/features/accounting/TelegramHtml";
import { formatNumber } from "@/lib/format";

type Action = {
  key: string;
  label: string;
  icon: typeof Bold;
  wrap: [string, string];
  placeholder: string;
};

/**
 * The buttons only insert the tags Telegram itself understands. The server
 * sanitizes the same subset again, so pasted markup cannot slip through.
 * Copyable text uses `<code>` because Telegram has no native copy button.
 */
const ACTIONS: Action[] = [
  { key: "b", label: "درشت", icon: Bold, wrap: ["<b>", "</b>"], placeholder: "متن درشت" },
  { key: "i", label: "کج", icon: Italic, wrap: ["<i>", "</i>"], placeholder: "متن کج" },
  { key: "u", label: "زیرخط", icon: Underline, wrap: ["<u>", "</u>"], placeholder: "متن" },
  { key: "s", label: "خط خورده", icon: Strikethrough, wrap: ["<s>", "</s>"], placeholder: "متن" },
  {
    key: "code",
    label: "قابل کپی",
    icon: Code,
    wrap: ["<code>", "</code>"],
    placeholder: "NN-1234",
  },
  {
    key: "pre",
    label: "بلوک کد",
    icon: FileCode2,
    wrap: ["<pre>", "</pre>"],
    placeholder: "متن بلوک",
  },
  {
    key: "quote",
    label: "نقل قول",
    icon: Quote,
    wrap: ["<blockquote>", "</blockquote>"],
    placeholder: "نقل قول",
  },
  {
    key: "a",
    label: "لینک",
    icon: Link2,
    wrap: ['<a href="https://">', "</a>"],
    placeholder: "متن لینک",
  },
];

export function RichTextEditor({
  id,
  value,
  onChange,
  maxLength = 3500,
  placeholder,
  error,
  showPreview = true,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  maxLength?: number;
  placeholder?: string;
  error?: string;
  showPreview?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  const [focused, setFocused] = useState(false);

  function apply(action: Action) {
    const textarea = ref.current;
    if (!textarea) return;
    const start = textarea.selectionStart ?? value.length;
    const end = textarea.selectionEnd ?? value.length;
    const selected = value.slice(start, end) || action.placeholder;
    const [open, close] = action.wrap;
    const next = `${value.slice(0, start)}${open}${selected}${close}${value.slice(end)}`;
    onChange(next.slice(0, maxLength));
    const caret = start + open.length;
    requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(caret, caret + selected.length);
    });
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-1 rounded-lg border border-line/60 bg-elevated/40 p-1">
        {ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.key}
              type="button"
              onClick={() => apply(action)}
              title={action.label}
              aria-label={action.label}
              className="rounded-md p-1.5 text-muted transition hover:bg-white/5 hover:text-ink"
            >
              <Icon size={15} aria-hidden />
            </button>
          );
        })}
        <span className="mr-auto pr-1 text-[10px] text-muted">
          {formatNumber(value.length)} از {formatNumber(maxLength)}
        </span>
      </div>

      <textarea
        id={id}
        ref={ref}
        className="field-input min-h-[150px] font-mono text-[11px] leading-6"
        dir="rtl"
        value={value}
        placeholder={placeholder}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(event) => onChange(event.target.value.slice(0, maxLength))}
        aria-invalid={error ? "true" : undefined}
      />

      {showPreview && (
        <div
          className={
            focused
              ? "rounded-lg border border-accent/40 bg-bg/60 p-3"
              : "rounded-lg border border-line/60 bg-bg/60 p-3"
          }
        >
          <div className="mb-1 text-[10px] text-muted">پیش نمایش در تلگرام</div>
          <div className="whitespace-pre-wrap text-xs leading-6">
            {value.trim() ? (
              <TelegramHtml html={value} />
            ) : (
              <span className="text-muted">متن پیام اینجا نمایش داده می شود.</span>
            )}
          </div>
        </div>
      )}

      {error ? <p className="field-error">{error}</p> : null}
    </div>
  );
}
