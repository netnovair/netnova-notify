"use client";

import { FlaskConical, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { InlineAlert, SkeletonRows } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage, queryString } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import type { Page, ProjectListItem } from "@/types/api";

export function DemoDataCard() {
  const { notify } = useToast();
  const projects = useApiData<Page<ProjectListItem>>(
    (signal) =>
      api.get<Page<ProjectListItem>>(
        `/projects${queryString({ include_archived: "true", page_size: 100 })}`,
        signal,
      ),
    [],
  );
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<number | null>(null);

  const demoProjects = (projects.data?.items ?? []).filter((project) => project.is_demo);

  async function purge() {
    setBusy(true);
    setError(null);
    try {
      const response = await api.post<{ deleted: number }>(
        `/projects/demo-purge?confirm=${encodeURIComponent(confirm.trim())}`,
      );
      setResult(response.deleted);
      setConfirm("");
      notify(`${formatNumber(response.deleted)} پروژه نمایشی حذف شد.`, "success");
      projects.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel p-5 lg:col-span-2">
      <div className="mb-3 flex items-center gap-2">
        <FlaskConical size={17} className="text-[#b9a7ff]" aria-hidden />
        <h2 className="text-sm font-semibold">داده های نمایشی</h2>
        {projects.data ? (
          <Badge tone={demoProjects.length > 0 ? "warning" : "neutral"}>
            {formatNumber(demoProjects.length)} پروژه نمایشی
          </Badge>
        ) : null}
      </div>
      <p className="mb-3 text-[11px] leading-6 text-muted">
        پروژه هایی که با اسکریپت نمونه سازی ساخته شده اند یا خودشان با پرچم «نمایشی» ثبت
        شده اند. حذف این داده ها فقط روی همین پروژه ها اثر دارد و به پروژه های واقعی
        کاری ندارد. هر حذف در تاریخچه فعالیت ثبت می شود.
      </p>

      {error ? (
        <div className="mb-2">
          <InlineAlert tone="danger">{error}</InlineAlert>
        </div>
      ) : null}
      {result !== null ? (
        <div className="mb-2">
          <InlineAlert tone="success">
            {result === 0
              ? "پروژه نمایشی برای حذف وجود نداشت."
              : `${formatNumber(result)} پروژه نمایشی حذف شد.`}
          </InlineAlert>
        </div>
      ) : null}

      {projects.loading && !projects.data ? (
        <SkeletonRows rows={2} />
      ) : demoProjects.length === 0 ? (
        <p className="text-[11px] text-muted">
          در حال حاضر پروژه ای با پرچم نمایشی وجود ندارد.
        </p>
      ) : (
        <>
          <ul className="mb-3 space-y-1">
            {demoProjects.map((project) => (
              <li key={project.id} className="flex items-center gap-2 text-[11px]">
                <Badge tone="info">نمایشی</Badge>
                <span>{project.name}</span>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-[11px]">
              <span className="mb-1 block text-muted">
                برای تایید، عبارت <code dir="ltr">DEMO</code> را بنویسید
              </span>
              <input
                dir="ltr"
                value={confirm}
                onChange={(event) => setConfirm(event.target.value)}
                className="h-9 w-40 rounded-lg border border-line bg-bg/60 px-2 text-xs"
                placeholder="DEMO"
              />
            </label>
            <Button
              variant="danger"
              size="sm"
              onClick={() => void purge()}
              loading={busy}
              disabled={confirm.trim().toUpperCase() !== "DEMO"}
            >
              <Trash2 size={13} aria-hidden />
              حذف داده های نمایشی
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
