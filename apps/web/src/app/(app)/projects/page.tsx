"use client";

import clsx from "clsx";
import {
  ChevronLeft,
  FolderKanban,
  Plus,
  Search,
  Send,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge, DemoBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/States";
import { ProjectStatusBadge } from "@/components/ui/StatusBadge";
import { LicenseRevealModal } from "@/features/licenses/LicenseRevealModal";
import { ProjectFormModal } from "@/features/projects/ProjectFormModal";
import { api, queryString } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { LICENSE_STATUS, labelFor } from "@/lib/labels";
import { useApiData, useDebouncedValue } from "@/lib/hooks";
import type { Page, ProjectCreated, ProjectListItem } from "@/types/api";

function LicenseChip({ project }: { project: ProjectListItem }) {
  if (!project.license_status) {
    return <Badge tone="neutral">بدون لایسنس</Badge>;
  }
  const spec = labelFor(LICENSE_STATUS, project.license_status);
  return <Badge tone={spec.tone}>{spec.label}</Badge>;
}

export default function ProjectsPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [created, setCreated] = useState<ProjectCreated | null>(null);
  const debouncedSearch = useDebouncedValue(search);

  const projects = useApiData<Page<ProjectListItem>>(
    (signal) =>
      api.get<Page<ProjectListItem>>(
        `/projects${queryString({
          search: debouncedSearch,
          status,
          page,
          page_size: 20,
        })}`,
        signal,
      ),
    [debouncedSearch, status, page],
  );

  const hasFilters = Boolean(debouncedSearch || status);
  const data = projects.data;

  return (
    <>
      <PageHeader
        eyebrow="مدیریت"
        title="پروژه ها"
        subtitle="هر پروژه لایسنس، قابلیت ها و کارفرمای مستقل خود را دارد."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <Plus size={16} aria-hidden />
            پروژه جدید
          </Button>
        }
      />

      <div className="panel mb-4 flex flex-col gap-3 p-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search
            size={16}
            className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-muted"
            aria-hidden
          />
          <input
            type="search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="جستجو بر اساس نام پروژه، کارفرما یا شناسه"
            className="field-input ps-9"
            aria-label="جستجوی پروژه"
          />
        </div>
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
          className="field-input sm:w-44"
          aria-label="فیلتر وضعیت پروژه"
        >
          <option value="">همه وضعیت ها</option>
          <option value="active">فعال</option>
          <option value="inactive">غیرفعال</option>
        </select>
      </div>

      <div className="panel overflow-hidden">
        {projects.error && !data ? (
          <ErrorState message={projects.error} onRetry={projects.reload} />
        ) : projects.loading && !data ? (
          <SkeletonRows rows={6} />
        ) : data && data.items.length === 0 ? (
          <EmptyState
            icon={<FolderKanban size={24} aria-hidden />}
            title={hasFilters ? "پروژه ای با این فیلتر یافت نشد" : "هنوز پروژه ای ثبت نشده است"}
            description={
              hasFilters
                ? "عبارت جستجو یا فیلتر وضعیت را تغییر دهید."
                : "اولین پروژه را ایجاد کنید تا لایسنس اختصاصی آن صادر شود."
            }
            action={
              hasFilters ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setSearch("");
                    setStatus("");
                  }}
                >
                  پاک کردن فیلترها
                </Button>
              ) : (
                <Button onClick={() => setCreateOpen(true)}>
                  <Plus size={16} aria-hidden />
                  ایجاد پروژه
                </Button>
              )
            }
          />
        ) : data ? (
          <>
            <div className="hidden overflow-x-auto lg:block">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>پروژه</th>
                    <th>وضعیت</th>
                    <th>کارفرما</th>
                    <th>لایسنس</th>
                    <th>اطلاعیه ها</th>
                    <th>پرداخت باز</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((project) => (
                    <tr key={project.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/projects/${project.id}`}
                            className="font-medium text-ink hover:text-[#c6b8ff]"
                          >
                            {project.name}
                          </Link>
                          {project.is_demo ? <DemoBadge /> : null}
                        </div>
                        <p className="mt-0.5 text-[11px] text-muted">
                          {project.client_name} · {project.slug}
                        </p>
                      </td>
                      <td>
                        <ProjectStatusBadge status={project.status} />
                      </td>
                      <td className="text-xs">
                        {project.telegram_connected && project.employer ? (
                          <span className="text-[#a5efd4]">
                            متصل · {project.employer.display_name}
                          </span>
                        ) : (
                          <span className="text-muted">بدون اتصال</span>
                        )}
                      </td>
                      <td>
                        <LicenseChip project={project} />
                      </td>
                      <td className="text-xs">
                        <span className="inline-flex items-center gap-1.5 text-muted">
                          <Send size={12} aria-hidden />
                          {formatNumber(project.notifications_count)}
                        </span>
                      </td>
                      <td className="text-xs">
                        <span
                          className={clsx(
                            "inline-flex items-center gap-1.5",
                            project.open_payments_count > 0 ? "text-[#f7d478]" : "text-muted",
                          )}
                        >
                          <Wallet size={12} aria-hidden />
                          {formatNumber(project.open_payments_count)}
                        </span>
                      </td>
                      <td>
                        <Link
                          href={`/projects/${project.id}`}
                          className="inline-flex items-center gap-1 text-[11px] text-muted transition hover:text-ink"
                        >
                          جزئیات
                          <ChevronLeft size={12} aria-hidden />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <ul className="divide-y divide-line-soft lg:hidden">
              {data.items.map((project) => (
                <li key={project.id}>
                  <Link href={`/projects/${project.id}`} className="block p-4 hover:bg-elevated/30">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate font-medium text-ink">{project.name}</span>
                          {project.is_demo ? <DemoBadge /> : null}
                        </div>
                        <p className="mt-0.5 truncate text-[11px] text-muted">
                          {project.client_name}
                        </p>
                      </div>
                      <ProjectStatusBadge status={project.status} />
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <LicenseChip project={project} />
                      <Badge tone={project.telegram_connected ? "success" : "neutral"}>
                        {project.telegram_connected
                          ? `کارفرما: ${project.employer?.display_name ?? "متصل"}`
                          : "بدون کارفرما"}
                      </Badge>
                    </div>
                    <div className="mt-3 flex items-center gap-4 text-[11px] text-muted">
                      <span className="inline-flex items-center gap-1">
                        <Send size={12} aria-hidden />
                        {formatNumber(project.notifications_count)} اطلاعیه
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Wallet size={12} aria-hidden />
                        {formatNumber(project.open_payments_count)} پرداخت باز
                      </span>
                      <ChevronLeft size={14} className="ms-auto" aria-hidden />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>

            <Pagination page={data} onChange={setPage} label="پروژه" />
          </>
        ) : null}
      </div>

      {createOpen ? (
        <ProjectFormModal
          open
          onClose={() => setCreateOpen(false)}
          onSaved={(project) => {
            setCreated(project);
            projects.reload();
          }}
        />
      ) : null}
      <LicenseRevealModal
        open={Boolean(created)}
        onClose={() => setCreated(null)}
        code={created?.license_code ?? null}
        projectName={created?.name}
      />
    </>
  );
}
