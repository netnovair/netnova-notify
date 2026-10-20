"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { TicketsWorkspace } from "@/features/tickets/TicketsWorkspace";

export default function TicketsPage() {
  return (
    <>
      <PageHeader
        eyebrow="پشتیبانی"
        title="تیکت ها"
        subtitle="گفتگوی دوطرفه با کارفرماها: پیام های ربات و پاسخ های پنل در یک جا."
      />
      <TicketsWorkspace />
    </>
  );
}
