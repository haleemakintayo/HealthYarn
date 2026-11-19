import React from "react";
import { t } from "../i18n";
import type { Lang } from "../types";

export interface StepProgressBarProps {
  lang: Lang;
  step: 1 | 2 | 3;
}

export const StepProgressBar: React.FC<StepProgressBarProps> = ({ lang, step }) => {
  const steps: Array<{ num: 1 | 2 | 3; label: string }> = [
    { num: 1, label: t(lang, "stepAsk") },
    { num: 2, label: t(lang, "stepChoose") },
    { num: 3, label: t(lang, "stepAnswer") }
  ];

  return (
    <nav
      aria-label={t(lang, "stepProgressLabel")}
      className="max-w-2xl mx-auto px-4 pt-4 pb-1"
    >
      <ol className="flex items-center gap-1.5 sm:gap-2">
        {steps.map((item) => {
          const isCurrent = item.num === step;
          const isDone = item.num < step;
          return (
            <li
              key={item.num}
              aria-current={isCurrent ? "step" : undefined}
              className={`flex-auto min-h-[38px] px-2.5 sm:px-3.5 py-1.5 rounded-full border text-xs sm:text-sm flex items-center justify-center gap-1.5 transition-colors whitespace-nowrap ${
                isCurrent
                  ? "bg-viridian border-viridian text-white font-bold shadow-sm"
                  : isDone
                  ? "bg-viridian-soft border-viridian/30 text-viridian font-semibold"
                  : "bg-surface border-seam text-ink-muted font-medium"
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full text-xs flex items-center justify-center tabular-nums shrink-0 ${
                  isCurrent
                    ? "bg-white text-viridian font-bold"
                    : isDone
                    ? "bg-viridian text-white font-bold"
                    : "bg-subtle text-ink-muted font-semibold"
                }`}
              >
                {item.num}
              </span>
              <span>{item.label}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
};
