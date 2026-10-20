"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { OrdersWorkspace } from "@/features/orders/OrdersWorkspace";

export default function OrdersPage() {
  return (
    <>
      <PageHeader
        eyebrow="فروش"
        title="سفارش ها"
        subtitle="درخواست هایی که از گفتگوی «ثبت سفارش» ربات تلگرام ثبت شده اند."
      />
      <OrdersWorkspace />
    </>
  );
}
