"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { ServicesWorkspace } from "@/features/services/ServicesWorkspace";

export default function ServicesPage() {
  return (
    <>
      <PageHeader
        eyebrow="ربات"
        title="خدمات و ثبت سفارش"
        subtitle="دسته ها، زیرخدمت ها و سوال های گفتگوی «ثبت سفارش» را همین جا مدیریت کنید."
      />
      <ServicesWorkspace />
    </>
  );
}
