"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";

export function CopyButton({
  value,
  label = "کپی",
  successMessage = "در حافظه کپی شد.",
  variant = "secondary",
  size = "sm",
  disabled = false,
}: {
  value: string;
  label?: string;
  successMessage?: string;
  variant?: "primary" | "secondary" | "ghost" | "subtle";
  size?: "sm" | "md";
  disabled?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const { notify } = useToast();

  async function copy() {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        const area = document.createElement("textarea");
        area.value = value;
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        document.execCommand("copy");
        document.body.removeChild(area);
      }
      setCopied(true);
      notify(successMessage, "success");
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      notify("کپی خودکار ممکن نشد. متن را دستی انتخاب کنید.", "error");
    }
  }

  return (
    <Button variant={variant} size={size} onClick={copy} disabled={disabled} type="button">
      {copied ? <Check size={14} aria-hidden /> : <Copy size={14} aria-hidden />}
      {label}
    </Button>
  );
}
