"use client";

import clsx from "clsx";
import {
  ArrowLeft,
  CheckCheck,
  ImagePlus,
  MessageSquarePlus,
  RefreshCw,
  Send,
  X,
  XCircle,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { EmptyState, ErrorState, InlineAlert, SkeletonRows } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { TelegramHtml } from "@/features/accounting/TelegramHtml";
import { RichTextEditor } from "@/features/rich-text/RichTextEditor";
import { api, errorMessage, queryString } from "@/lib/api";
import { formatDateTime, formatNumber, formatRelative } from "@/lib/format";
import { useApiData } from "@/lib/hooks";
import { TICKET_PRIORITY, TICKET_STATUS } from "@/lib/labels";
import type {
  Page,
  ProjectListItem,
  Ticket,
  TicketAttachment,
  TicketListItem,
} from "@/types/api";

const STATUS_FILTERS: Array<{ value: string; label: string }> = [
  { value: "", label: "همه" },
  { value: "pending_admin", label: "در انتظار پاسخ ما" },
  { value: "pending_employer", label: "در انتظار کارفرما" },
  { value: "closed", label: "بسته شده" },
];

const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_IMAGES = 4;
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${formatNumber(bytes)} بایت`;
  return `${formatNumber(Math.round(bytes / 1024))} کیلوبایت`;
}

function AttachmentImage({ attachment }: { attachment: TicketAttachment }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    let objectUrl: string | null = null;
    api
      .getBlob(`/tickets/attachments/${attachment.id}`)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (!active) {
          URL.revokeObjectURL(objectUrl);
          return;
        }
        setUrl(objectUrl);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [attachment.id]);

  return (
    <figure className="max-w-full overflow-hidden rounded-lg border border-line bg-bg/60">
      {url ? (
        <a href={url} target="_blank" rel="noreferrer" title="باز کردن تصویر">
          <img
            src={url}
            alt={attachment.filename}
            className="max-h-44 w-auto max-w-full object-contain"
          />
        </a>
      ) : failed ? (
        <div className="px-3 py-6 text-[10px] text-muted">تصویر در دسترس نیست</div>
      ) : (
        <div className="h-24 w-32 animate-pulse bg-white/5" aria-label="در حال بارگذاری تصویر" />
      )}
      <figcaption className="px-2 py-1 text-[9px] text-muted">
        {attachment.filename} · {formatFileSize(attachment.size_bytes)}
      </figcaption>
    </figure>
  );
}

function StatusBadge({ status }: { status: string }) {
  const spec = TICKET_STATUS[status] ?? { label: status, tone: "neutral" as const };
  return <Badge tone={spec.tone}>{spec.label}</Badge>;
}

function TicketDetailPanel({
  ticketId,
  onChanged,
}: {
  ticketId: string;
  onChanged: () => void;
}) {
  const { notify } = useToast();
  const ticket = useApiData<Ticket>(
    (signal) => api.get<Ticket>(`/tickets/${ticketId}`, signal),
    [ticketId],
  );
  const [reply, setReply] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function pickFiles(event: React.ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(event.target.files ?? []);
    event.target.value = "";
    const accepted: File[] = [];
    for (const file of picked) {
      if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
        setError("فقط تصویر JPEG، PNG، WebP یا GIF پذیرفته می شود.");
        continue;
      }
      if (file.size > MAX_IMAGE_BYTES) {
        setError("حجم هر تصویر حداکثر ۵ مگابایت است.");
        continue;
      }
      accepted.push(file);
    }
    const next = [...files, ...accepted];
    if (next.length > MAX_IMAGES) {
      setError(`حداکثر ${formatNumber(MAX_IMAGES)} تصویر در هر پیام ارسال کنید.`);
    }
    setFiles(next.slice(0, MAX_IMAGES));
  }

  function removeFile(index: number) {
    setFiles(files.filter((_, position) => position !== index));
  }

  async function sendReply() {
    if (!ticket.data) return;
    const text = reply.trim();
    if (files.length === 0 && text.length < 2) return;
    setBusy(true);
    setError(null);
    try {
      if (files.length > 0) {
        const form = new FormData();
        form.set("body", text);
        files.forEach((file) => form.append("files", file, file.name));
        await api.upload(`/tickets/${ticketId}/attachments`, form);
      } else {
        await api.post(`/tickets/${ticketId}/reply`, { body: text });
      }
      setReply("");
      setFiles([]);
      notify(
        files.length > 0
          ? "پاسخ و تصویرها ثبت شد و برای کارفرما در تلگرام ارسال می شود."
          : "پاسخ ثبت شد و برای کارفرما در تلگرام ارسال می شود.",
        "success",
      );
      ticket.reload();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(status: string) {
    setBusy(true);
    setError(null);
    try {
      await api.patch(`/tickets/${ticketId}/status`, { status });
      notify(status === "closed" ? "تیکت بسته شد." : "وضعیت تیکت تغییر کرد.", "success");
      ticket.reload();
      onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (ticket.error && !ticket.data) {
    return <ErrorState message={ticket.error} onRetry={ticket.reload} compact />;
  }
  if (ticket.loading && !ticket.data) {
    return <SkeletonRows rows={4} />;
  }
  const data = ticket.data;
  if (!data) return null;

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-line px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold">{data.subject}</h2>
          <StatusBadge status={data.status} />
        </div>
        <p className="mt-1 text-[11px] text-muted">
          {data.project_name} · ثبت {formatDateTime(data.created_at)} ·{" "}
          {data.message_count} پیام
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {data.status !== "closed" ? (
            <Button size="sm" variant="secondary" onClick={() => void setStatus("closed")} loading={busy}>
              <CheckCheck size={13} aria-hidden />
              بستن تیکت
            </Button>
          ) : (
            <Button size="sm" variant="secondary" onClick={() => void setStatus("open")} loading={busy}>
              <XCircle size={13} aria-hidden />
              بازگشایی
            </Button>
          )}
        </div>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {data.messages.map((message) => {
          const mine = message.author_type === "admin";
          return (
            <div
              key={message.id}
              className={clsx(
                "max-w-[95%] rounded-xl border px-3 py-2 text-xs leading-6",
                mine
                  ? "ms-auto border-accent/25 bg-accent/10 text-ink"
                  : "border-line bg-elevated/60 text-ink",
              )}
            >
              <div className="mb-1 flex items-center justify-between gap-3 text-[10px] text-muted">
                <span>{mine ? "پشتیبانی" : message.author_label || "کارفرما"}</span>
                <span>{formatDateTime(message.created_at)}</span>
              </div>
              {mine ? (
                <div className="whitespace-pre-wrap">
                  <TelegramHtml html={message.body} />
                </div>
              ) : (
                <p className="whitespace-pre-wrap">{message.body}</p>
              )}
              {message.attachments.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {message.attachments.map((attachment) => (
                    <AttachmentImage key={attachment.id} attachment={attachment} />
                  ))}
                </div>
              ) : null}
              <p className="mt-1 text-[9px] text-muted/70">
                کانال: {message.channel === "telegram" ? "ربات تلگرام" : "پنل مدیریت"}
              </p>
            </div>
          );
        })}
      </div>

      <footer className="border-t border-line px-4 py-3">
        {error ? (
          <div className="mb-2">
            <InlineAlert tone="danger">{error}</InlineAlert>
          </div>
        ) : null}
        <label htmlFor="ticket-reply" className="mb-1 block text-[11px] text-muted">
          پاسخ شما
        </label>
        <RichTextEditor
          id="ticket-reply"
          value={reply}
          onChange={setReply}
          maxLength={4000}
          placeholder="پاسخ برای کارفرما..."
          showPreview={false}
        />
        {files.length > 0 ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {files.map((file, index) => (
              <span
                key={`${file.name}-${index}`}
                className="inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-[10px]"
              >
                {file.name}
                <button
                  type="button"
                  onClick={() => removeFile(index)}
                  aria-label={`حذف ${file.name}`}
                  className="text-muted hover:text-ink"
                >
                  <X size={11} aria-hidden />
                </button>
              </span>
            ))}
          </div>
        ) : null}
        <div className="mt-2 flex flex-wrap items-center justify-end gap-2">
          <input
            ref={fileInput}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            multiple
            hidden
            onChange={pickFiles}
          />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => fileInput.current?.click()}
            disabled={busy || files.length >= MAX_IMAGES}
            title="افزودن تصویر (حداکثر ۵ مگابایت)"
          >
            <ImagePlus size={13} aria-hidden />
            تصویر
          </Button>
          <Button
            size="sm"
            onClick={() => void sendReply()}
            loading={busy}
            disabled={files.length === 0 && reply.trim().length < 2}
          >
            <Send size={13} aria-hidden />
            ارسال پاسخ
          </Button>
        </div>
      </footer>
    </div>
  );
}

export function TicketsWorkspace({ projectId }: { projectId?: string }) {
  const { notify } = useToast();
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [version, setVersion] = useState(0);

  const tickets = useApiData<Page<TicketListItem>>(
    (signal) =>
      api.get<Page<TicketListItem>>(
        `/tickets${queryString({ status: status || undefined, project_id: projectId, page_size: 50 })}`,
        signal,
      ),
    [status, projectId, version],
  );

  const projects = useApiData<Page<ProjectListItem>>(
    (signal) => api.get<Page<ProjectListItem>>("/projects?page_size=100", signal),
    [],
  );

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <section className="panel flex min-h-[520px] flex-col">
        <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
          <div className="flex flex-wrap gap-1">
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                onClick={() => setStatus(filter.value)}
                className={clsx(
                  "rounded-md px-2 py-1 text-[10px] transition",
                  status === filter.value
                    ? "bg-accent/15 text-ink ring-1 ring-inset ring-accent/25"
                    : "text-muted hover:bg-white/5 hover:text-ink",
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>
          <div className="ms-auto flex items-center gap-1">
            <Button size="sm" variant="ghost" onClick={tickets.reload} aria-label="به روزرسانی">
              <RefreshCw size={13} aria-hidden />
            </Button>
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <MessageSquarePlus size={13} aria-hidden />
              تیکت جدید
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {tickets.error && !tickets.data ? (
            <ErrorState message={tickets.error} onRetry={tickets.reload} compact />
          ) : tickets.loading && !tickets.data ? (
            <SkeletonRows rows={5} />
          ) : tickets.data && tickets.data.items.length === 0 ? (
            <EmptyState
              title="تیکتی وجود ندارد"
              description={
                status
                  ? "در این وضعیت تیکتی ثبت نشده است."
                  : "کارفرما می تواند از منوی ربات برای پروژه تیکت ثبت کند."
              }
            />
          ) : (
            <ul>
              {tickets.data?.items.map((ticket) => (
                <li key={ticket.id}>
                  <button
                    type="button"
                    onClick={() => setSelected(ticket.id)}
                    className={clsx(
                      "w-full border-b border-line-soft px-3 py-2.5 text-start transition",
                      selected === ticket.id ? "bg-accent/10" : "hover:bg-white/5",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <span className="truncate text-xs font-medium">{ticket.subject}</span>
                      {ticket.admin_unread > 0 ? (
                        <Badge tone="danger">{ticket.admin_unread} جدید</Badge>
                      ) : null}
                      <span className="ms-auto text-[10px] text-muted">
                        {formatRelative(ticket.last_message_at)}
                      </span>
                    </div>
                    <p className="mt-1 truncate text-[11px] text-muted">
                      {ticket.project_name} · {ticket.preview ?? "بدون پیام"}
                    </p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <StatusBadge status={ticket.status} />
                      {ticket.priority !== "normal" ? (
                        <Badge tone={TICKET_PRIORITY[ticket.priority]?.tone ?? "neutral"}>
                          {TICKET_PRIORITY[ticket.priority]?.label ?? ticket.priority}
                        </Badge>
                      ) : null}
                      {ticket.is_overdue ? <Badge tone="danger">پیگیری معوق</Badge> : null}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>

      <section className="panel min-h-[520px] overflow-hidden">
        {selected ? (
          <TicketDetailPanel
            ticketId={selected}
            onChanged={() => {
              setVersion((value) => value + 1);
            }}
          />
        ) : (
          <div className="flex h-full items-center justify-center p-6">
            <EmptyState
              title="یک تیکت را انتخاب کنید"
              description="برای دیدن گفتگو، پاسخ و تغییر وضعیت، یک تیکت را از فهرست کنار انتخاب کنید."
            />
          </div>
        )}
      </section>

      {createOpen ? (
        <NewTicketModal
          projects={projects.data?.items ?? []}
          fixedProjectId={projectId}
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            setVersion((value) => value + 1);
            notify("تیکت ثبت شد.", "success");
          }}
        />
      ) : null}
    </div>
  );
}

function NewTicketModal({
  projects,
  fixedProjectId,
  onClose,
  onCreated,
}: {
  projects: ProjectListItem[];
  fixedProjectId?: string;
  onClose: () => void;
  onCreated: (ticket: Ticket) => void;
}) {
  const [projectId, setProjectId] = useState(fixedProjectId ?? projects[0]?.id ?? "");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [priority, setPriority] = useState("normal");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const created = await api.post<Ticket>("/tickets", {
        project_id: projectId,
        subject,
        body,
        priority,
      });
      onCreated(created);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="تیکت جدید برای کارفرما"
      description="این تیکت در پنل و در ربات کارفرما نمایش داده می شود."
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={busy}>
            انصراف
          </Button>
          <Button
            onClick={() => void submit()}
            loading={busy}
            disabled={!projectId || subject.trim().length < 2 || body.trim().length < 2}
          >
            <ArrowLeft size={14} aria-hidden />
            ثبت تیکت
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {error ? <InlineAlert tone="danger">{error}</InlineAlert> : null}
        {!fixedProjectId ? (
          <label className="block text-xs">
            <span className="mb-1 block text-muted">پروژه</span>
            <select
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              className="h-9 w-full rounded-lg border border-line bg-bg/60 px-2 text-xs"
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <label className="block text-xs">
          <span className="mb-1 block text-muted">موضوع</span>
          <input
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            maxLength={200}
            className="h-9 w-full rounded-lg border border-line bg-bg/60 px-2 text-xs"
          />
        </label>
        <label className="block text-xs">
          <span className="mb-1 block text-muted">متن</span>
          <textarea
            value={body}
            onChange={(event) => setBody(event.target.value)}
            rows={5}
            maxLength={4000}
            className="w-full resize-y rounded-lg border border-line bg-bg/60 px-2 py-2 text-xs leading-6"
          />
        </label>
        <label className="block text-xs">
          <span className="mb-1 block text-muted">اولویت</span>
          <select
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
            className="h-9 w-full rounded-lg border border-line bg-bg/60 px-2 text-xs"
          >
            <option value="low">کم</option>
            <option value="normal">معمولی</option>
            <option value="high">فوری</option>
          </select>
        </label>
        <p className="text-[10px] leading-6 text-muted">
          برای کارفرما فقط خلاصه پیام و دکمه ورود به فهرست تیکت ها ارسال می شود؛ متن کامل در
          ربات باقی می ماند.
        </p>
      </div>
    </Modal>
  );
}
