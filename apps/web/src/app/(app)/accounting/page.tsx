"use client";

import { CreditCard, FileText, Landmark, ReceiptText } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonRows } from "@/components/ui/States";
import { OverviewPanel } from "@/features/accounting/OverviewPanel";
import { PaymentMethodsPanel } from "@/features/accounting/PaymentMethodsPanel";
import { ReceiptsPanel } from "@/features/accounting/ReceiptsPanel";
import { TemplatesPanel } from "@/features/accounting/TemplatesPanel";
import { api } from "@/lib/api";
import { useApiData } from "@/lib/hooks";
import type { Page, ProjectListItem } from "@/types/api";

const TABS = [
  { key: "overview", label: "خلاصه مالی", icon: Landmark },
  { key: "receipts", label: "رسیدها", icon: ReceiptText },
  { key: "cards", label: "شماره کارت ها", icon: CreditCard },
  { key: "templates", label: "متن های آماده", icon: FileText },
] as const;

type TabKey = (typeof TABS)[number]["key"];

function AccountingContent() {
  const params = useSearchParams();
  const initialTab = params.get("tab");
  const [tab, setTab] = useState<TabKey>(
    initialTab === "receipts" || initialTab === "cards" || initialTab === "templates"
      ? initialTab
      : "overview",
  );
  const [refreshKey, setRefreshKey] = useState(0);

  const projects = useApiData<Page<ProjectListItem>>(
    (signal) => api.get<Page<ProjectListItem>>("/projects?page_size=100", signal),
    [],
  );

  const projectItems = projects.data?.items ?? [];
  const refresh = () => setRefreshKey((value) => value + 1);

  return (
    <>
      <PageHeader
        eyebrow="مدیریت"
        title="حسابداری"
        subtitle="بدهی و مانده حساب هر پروژه، بررسی رسیدهای کارفرما، شماره کارت ها و متن های آماده ربات."
      />

      <div className="mb-4 flex flex-wrap gap-1 rounded-xl border border-line/60 bg-black/10 p-1">
        {TABS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => setTab(item.key)}
              className={
                tab === item.key
                  ? "inline-flex items-center gap-2 rounded-lg bg-accent/15 px-3 py-2 text-xs text-accent"
                  : "inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted transition hover:bg-white/5"
              }
              aria-pressed={tab === item.key}
            >
              <Icon size={15} aria-hidden />
              {item.label}
            </button>
          );
        })}
      </div>

      {projects.loading ? (
        <SkeletonRows rows={3} />
      ) : tab === "overview" ? (
        <OverviewPanel refreshKey={refreshKey} />
      ) : tab === "receipts" ? (
        <ReceiptsPanel projects={projectItems} refreshKey={refreshKey} onChanged={refresh} />
      ) : tab === "cards" ? (
        <PaymentMethodsPanel projects={projectItems} refreshKey={refreshKey} onChanged={refresh} />
      ) : (
        <TemplatesPanel projects={projectItems} refreshKey={refreshKey} onChanged={refresh} />
      )}
    </>
  );
}

export default function AccountingPage() {
  return (
    <Suspense fallback={<SkeletonRows rows={4} />}>
      <AccountingContent />
    </Suspense>
  );
}
