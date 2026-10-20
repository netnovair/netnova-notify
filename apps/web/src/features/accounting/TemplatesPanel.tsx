"use client";

import { RotateCcw, Save } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ui/Modal";
import { ErrorState, InlineAlert, SkeletonRows } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import type { MessageTemplate, ProjectListItem } from "@/types/api";

import { TelegramHtml } from "./TelegramHtml";

const SAMPLE: Record<string, string> = {
  project: "فروشگاه آرمان",
  name: "سارا محمدی",
  amount: "۲,۵۰۰,۰۰۰ تومان",
  due: "۱۰ آذر ۱۴۰۵",
  remaining: "۱,۲۰۰,۰۰۰ تومان",
  status: "تسویه",
  cards: "بانک ملی\n6037 9977 1122 3344",
  license: "NN-4K7P-93XD",
  tracking: "123456789",
  reason: "تصویر رسید خوانا نیست.",
};

export function TemplatesPanel({
  projects,
  refreshKey,
  onChanged,
}: {
  projects: ProjectListItem[];
  refreshKey: number;
  onChanged: () => void;
}) {
  const [scope, setScope] = useState("");
  const [activeKey, setActiveKey] = useState<string>("");

  const templates = useApiData<MessageTemplate[]>(
    (signal) =>
      api.get<MessageTemplate[]>(
        `/accounting/templates${scope ? `?project_id=${scope}` : ""}`,
        signal,
      ),
    [scope, refreshKey],
  );

  const rows = templates.data ?? [];
  const active = rows.find((row) => row.key === activeKey) ?? null;

  if (templates.loading) return <SkeletonRows rows={4} />;
  if (templates.error)
    return <ErrorState message={templates.error} onRetry={templates.reload} />;

  return (
    <div className="space-y-4">
      <InlineAlert>
        این متن ها در پیام های ربات استفاده می شوند. فقط تگ های رسمی تلگرام پشتیبانی می شوند:
        <span dir="ltr" className="mx-1 font-mono text-[11px]">
          {"<b> <i> <u> <s> <code> <pre> <blockquote> <a href>"}
        </span>
        برای متن قابل کپی از تگ code استفاده کنید. لینک فقط با http یا https پذیرفته می شود.
      </InlineAlert>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <select
          className="field-input sm:w-64"
          value={scope}
          onChange={(event) => {
            setScope(event.target.value);
            setActiveKey("");
          }}
          aria-label="دامنه متن"
        >
          <option value="">متن پیش فرض (همه پروژه ها)</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        {scope && (
          <span className="text-[11px] text-muted">
            متن پروژه بر متن عمومی اولویت دارد؛ اگر خالی بماند متن عمومی استفاده می شود.
          </span>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,240px)_minmax(0,1fr)]">
        <div className="panel space-y-1 p-2">
          {rows.map((row) => (
            <button
              key={row.key}
              type="button"
              onClick={() => setActiveKey(row.key)}
              className={
                row.key === activeKey
                  ? "w-full rounded-lg bg-accent/15 px-3 py-2 text-right text-xs text-accent"
                  : "w-full rounded-lg px-3 py-2 text-right text-xs text-muted transition hover:bg-white/5"
              }
            >
              <span className="flex items-center justify-between gap-2">
                <span>{row.title}</span>
                {row.customized && <Badge tone="accent">سفارشی</Badge>}
              </span>
            </button>
          ))}
        </div>

        <div className="panel min-h-[280px] p-4">
          {!active ? (
            <p className="text-xs text-muted">یک متن را از فهرست انتخاب کنید.</p>
          ) : (
            <TemplateEditor
              key={`${scope}:${active.key}:${active.updated_at ?? "default"}`}
              template={active}
              scope={scope}
              onSaved={() => {
                templates.reload();
                onChanged();
              }}
            />
          )}
        </div>
      </div>

    </div>
  );
}

/** Replace placeholders with sample values; unknown ones stay visible. */
export function renderPreview(body: string, variables: string[]): string {
  let output = body;
  for (const variable of variables) {
    output = output.split(`{${variable}}`).join(SAMPLE[variable] ?? `{${variable}}`);
  }
  return output;
}

function TemplateEditor({
  template,
  scope,
  onSaved,
}: {
  template: MessageTemplate;
  scope: string;
  onSaved: () => void;
}) {
  const { notify } = useToast();
  const [body, setBody] = useState(template.body);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await api.put(`/accounting/templates/${template.key}`, {
        body,
        project_id: scope || null,
      });
      setDirty(false);
      notify("متن ذخیره شد.", "success");
      onSaved();
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    setSaving(true);
    try {
      await api.del(
        `/accounting/templates/${template.key}${scope ? `?project_id=${scope}` : ""}`,
      );
      setResetting(false);
      setDirty(false);
      notify("متن به حالت پیش فرض بازگشت.", "success");
      onSaved();
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setSaving(false);
    }
  }

  function insert(variable: string) {
    setBody((current) => `${current}{${variable}}`);
    setDirty(true);
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold">{template.title}</h3>
        <p className="mt-1 text-[11px] text-muted">{template.description}</p>
      </div>

      <label className="block">
        <span className="text-[11px] text-muted">متن پیام</span>
        <textarea
          className="field-input mt-1 min-h-[170px] font-mono text-[11px] leading-6"
          dir="rtl"
          value={body}
          onChange={(event) => {
            setBody(event.target.value);
            setDirty(true);
          }}
        />
      </label>

      <div className="flex flex-wrap gap-1">
        {template.variables.map((variable) => (
          <button
            key={variable}
            type="button"
            onClick={() => insert(variable)}
            className="rounded-md border border-line px-2 py-1 font-mono text-[10px] text-muted transition hover:border-accent/50 hover:text-accent"
            title={`درج {${variable}}`}
          >
            {`{${variable}}`}
          </button>
        ))}
      </div>

      <div>
        <div className="mb-1 text-[11px] text-muted">پیش نمایش (نمونه مقادیر)</div>
        <div className="whitespace-pre-wrap rounded-lg border border-line/60 bg-bg/60 p-3 text-xs leading-6">
          <TelegramHtml html={renderPreview(body, template.variables)} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button onClick={() => void save()} loading={saving} disabled={!dirty}>
          <Save size={15} aria-hidden />
          ذخیره متن
        </Button>
        <Button
          variant="ghost"
          onClick={() => setResetting(true)}
          disabled={!template.customized}
        >
          <RotateCcw size={15} aria-hidden />
          بازگشت به پیش فرض
        </Button>
      </div>
      {template.updated_at && (
        <p className="text-[10px] text-muted">
          آخرین ویرایش: {new Date(template.updated_at).toLocaleString("fa-IR")}
        </p>
      )}

      <ConfirmDialog
        open={resetting}
        onClose={() => setResetting(false)}
        onConfirm={reset}
        title="بازگشت به متن پیش فرض"
        message="متن سفارشی حذف می شود و متن پیش فرض جای آن را می گیرد. ادامه می دهید؟"
        confirmLabel="بازگردان"
        loading={saving}
      />
    </div>
  );
}
