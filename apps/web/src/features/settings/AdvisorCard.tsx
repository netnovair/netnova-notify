"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { InlineAlert } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { api, errorMessage } from "@/lib/api";
import { useApiData } from "@/lib/hooks";

type AdvisorStatus = {
  available: boolean;
  provider: string;
  model: string;
  reason: string;
};

const TOPICS = [
  "آماده سازی محتوا و متن برای سایت",
  "سئو مقدماتی و انتخاب کلمات کلیدی",
  "راهنمای استفاده از پنل و ربات",
  "گام های تحویل پروژه",
];

/**
 * The advisor is structurally ready but has no provider key. The card says so
 * and keeps the input disabled instead of faking answers.
 */
export function AdvisorCard({ refreshKey = 0 }: { refreshKey?: number }) {
  const { notify } = useToast();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const status = useApiData<AdvisorStatus>(
    (signal) => api.get<AdvisorStatus>("/advisor/status", signal),
    [refreshKey],
  );
  const available = status.data?.available === true;

  async function ask() {
    setBusy(true);
    try {
      const result = await api.post<{ answer: string }>("/advisor/ask", { question });
      setAnswer(result.answer);
    } catch (error) {
      notify(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel p-5" aria-labelledby="advisor-title">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Sparkles size={17} className="text-[#b9a7ff]" aria-hidden />
        <h2 id="advisor-title" className="text-sm font-semibold">
          مشاور هوشمند کارفرما
        </h2>
        {status.loading ? null : available ? (
          <Badge tone="success">فعال</Badge>
        ) : (
          <Badge tone="neutral">به زودی</Badge>
        )}
        {available && status.data?.model ? (
          <Badge tone="accent">{status.data.model}</Badge>
        ) : null}
      </div>

      <p className="text-[11px] leading-6 text-muted">
        پاسخ های کوتاه و آموزشی به سوالات کارفرما درباره محتوا، سئو و روند تحویل. پاسخ ها
        هرگز شامل عدد مالی، وضعیت پرداخت یا کد لایسنس نیستند و در صورت نبود کلید API،
        ربات پاسخ «به زودی» می دهد.
      </p>

      <ul className="mt-3 flex flex-wrap gap-1.5">
        {TOPICS.map((topic) => (
          <li
            key={topic}
            className="rounded-full border border-line px-2.5 py-1 text-[10px] text-muted"
          >
            {topic}
          </li>
        ))}
      </ul>

      <div className="mt-4 space-y-2">
        <label htmlFor="advisor-question" className="text-[11px] text-muted">
          پرسش آزمایشی
        </label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            id="advisor-question"
            className="field-input sm:flex-1"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            disabled={!available || busy}
            placeholder={
              available ? "مثلا: برای صفحه محصول چه متنی بنویسم؟" : "پس از تنظیم کلید API فعال می شود"
            }
          />
          <Button
            onClick={() => void ask()}
            loading={busy}
            disabled={!available || question.trim().length < 5}
          >
            پرسیدن
          </Button>
        </div>
        {!available && status.data ? (
          <InlineAlert tone="info">
            {status.data.reason} برای فعال سازی، مقدار AI_ADVISOR_PROVIDER و
            AI_ADVISOR_API_KEY را روی سرور تنظیم کنید.
          </InlineAlert>
        ) : null}
        {answer ? (
          <div className="rounded-lg border border-line/60 bg-bg/60 p-3 text-xs leading-6">
            {answer}
          </div>
        ) : null}
      </div>
    </section>
  );
}
