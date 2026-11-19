import React, { useEffect, useRef } from "react";
import { t } from "../i18n";
import type { Lang, QuestionSummary, TopicSummary } from "../types";
import { ArrowLeftIcon, ChevronRightIcon, TopicIcon, VolumeIcon } from "./Icons";

interface TopicDetailViewProps {
  lang: Lang;
  topic: TopicSummary;
  onBack: () => void;
  onSelectQuestion: (faqId: number) => void;
  onPlayQuestionAudio: (q: QuestionSummary) => void;
}

export const TopicDetailView: React.FC<TopicDetailViewProps> = ({
  lang,
  topic,
  onBack,
  onSelectQuestion,
  onPlayQuestionAudio
}) => {
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, [topic.slug]);

  return (
    <main className="max-w-2xl mx-auto px-4 py-5">
      <button
        type="button"
        onClick={onBack}
        aria-label={t(lang, "backTopics")}
        className="min-h-[48px] px-4 py-2 rounded-lg bg-surface border border-seam text-ink font-semibold inline-flex items-center gap-2 hover:bg-subtle transition-colors mb-5"
      >
        <ArrowLeftIcon className="w-5 h-5 text-viridian" />
        <span>{t(lang, "backTopics")}</span>
      </button>

      <div className="flex items-start gap-3 mb-4">
        <div className="w-12 h-12 rounded-card bg-hy-sand flex items-center justify-center shrink-0 border border-seam">
          <TopicIcon icon={topic.icon} className="w-7 h-7" />
        </div>
        <div>
          <h1
            ref={headingRef}
            tabIndex={-1}
            className="text-2xl font-bold text-ink leading-tight focus:outline-none"
          >
            {topic.name}
          </h1>
          {topic.description && (
            <p className="text-ink-muted text-base mt-1 prose-measure">{topic.description}</p>
          )}
        </div>
      </div>

      <p className="text-sm font-medium text-ink-muted mb-4">{t(lang, "topicTapHint")}</p>

      <ul className="space-y-3" aria-label={topic.name}>
        {topic.questions.map((q) => (
          <li
            key={q.faq_id}
            className="bg-surface border border-seam rounded-xl flex items-stretch overflow-hidden hover:border-viridian transition-colors"
          >
            <button
              type="button"
              onClick={() => onPlayQuestionAudio(q)}
              aria-label={`${t(lang, "playQuestionAudio")}: ${q.question}`}
              className="min-w-[56px] min-h-[60px] px-3 bg-viridian-soft text-viridian hover:bg-viridian hover:text-white flex items-center justify-center border-r border-seam transition-colors shrink-0"
            >
              <VolumeIcon className="w-6 h-6" />
            </button>
            <button
              type="button"
              onClick={() => onSelectQuestion(q.faq_id)}
              aria-label={`${t(lang, "openAnswer")}: ${q.question}`}
              className="flex-1 min-h-[60px] px-4 py-3.5 text-left flex items-center justify-between gap-3"
            >
              <span className="font-semibold text-ink text-base leading-snug">{q.question}</span>
              <ChevronRightIcon className="w-5 h-5 text-ink-muted shrink-0" />
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
};
