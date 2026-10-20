"use client";

import { MessagesSquare } from "lucide-react";

import { InlineAlert } from "@/components/ui/States";
import { TicketsWorkspace } from "@/features/tickets/TicketsWorkspace";
import type { Project } from "@/types/api";

export function ProjectTicketsTab({ project }: { project: Project }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs text-muted">
        <MessagesSquare size={15} className="text-[#b9a7ff]" aria-hidden />
        تیکت های پروژه «{project.name}»
      </div>
      {project.archived_at ? (
        <InlineAlert tone="warning">
          پروژه بایگانی شده است؛ تیکت جدید ثبت نمی شود ولی گفتگوهای قبلی قابل مشاهده و
          پاسخ هستند.
        </InlineAlert>
      ) : null}
      <TicketsWorkspace projectId={project.id} />
    </div>
  );
}
