import React, { useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import type { Lang, UnsureCandidate } from "../types";
import { ArrowLeftIcon, ChevronRightIcon, VolumeIcon } from "./Icons";

interface UnsureViewProps {
  lang: Lang;
  heardText?: string | null;
  messageText: string;
  messageAudioUrl: string | null;
  candidates: UnsureCandidate[];
  autoplayEnabled: boolean;
  onPlayClip: (url: string | null | undefined) => void;
  onSelectCandidate: (faqId: number) => void;
  onBackHome: () => void;
}

export const UnsureView: React.FC<UnsureViewProps> = ({
  lang,
  heardText,
  messageText,
  messageAudioUrl,
  candidates,
  autoplayEnabled,
  onPlayClip,
  onSelectCandidate,
  onBackHome
}) => {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
    setSelectedId(null);
    if (autoplayEnabled && messageAudioUrl) {
      onPlayClip(messageAudioUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messageAudioUrl]);

  const handleCardTap = (candidate: UnsureCandidate) => {
    if (selectedId === candidate.faq_id) {
      onSelectCandidate(candidate.faq_id);
      return;
    }
    setSelectedId(candidate.faq_id);
    onPlayClip(candidate.question_audio_url);
  };

  return (
    <main className="max-w-2xl mx-auto px-4 py-5">
      <button
        type="button"
        onClick={onBackHome}
        aria-label={t(lang, "backHome")}
        className="min-h-[48px] px-4 py-2 rounded-lg bg-surface border border-seam text-ink font-semibold inline-flex items-center gap-2 hover:bg-subtle transition-colors mb-5"
      >
        <ArrowLeftIcon className="w-5 h-5 text-viridian" />
        <span>{t(lang, "backHome")}</span>
      </button>

      <div className="bg-surface border border-seam rounded-2xl p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4 mb-2">
          <h1
            ref={headingRef}
            tabIndex={-1}
            className="text-2xl font-bold text-ink focus:outline-none"
          >
            {t(lang, "unsureTitle")}
          </h1>
          {messageAudioUrl && (
            <button
              type="button"
              onClick={() => onPlayClip(messageAudioUrl)}
              aria-label={t(lang, "playQuestionAudio")}
              className="min-w-[48px] min-h-[48px] rounded-xl bg-ochre-bg border border-ochre-border text-ochre flex items-center justify-center shrink-0"
            >
              <VolumeIcon className="w-6 h-6" />
            </button>
          )}
        </div>

        <p className="text-ink-muted prose-measure mb-4">
          {messageText || t(lang, "unsureHint")}
        </p>

        {heardText && (
          <p className="inline-block text-sm font-medium text-ink bg-ground border border-seam rounded-lg px-3 py-1.5 mb-4">
            “{heardText}”
          </p>
        )}

        <p className="text-sm font-semibold text-ochre bg-ochre-bg border border-ochre-border rounded-lg px-3.5 py-2.5 mb-5">
          {t(lang, "unsureHint")}
        </p>

        <div className="space-y-3">
          {candidates.map((c) => {
            const isPrimed = selectedId === c.faq_id;
            return (
              <div
                key={c.faq_id}
                className={`rounded-xl border transition-colors ${
                  isPrimed
                    ? "bg-viridian-soft border-viridian"
                    : "bg-ground border-seam hover:border-viridian"
                }`}
              >
                <div className="flex items-stretch">
                  <button
                    type="button"
                    onClick={() => handleCardTap(c)}
                    aria-label={c.question}
                    className="flex-1 min-h-[68px] px-4 py-3.5 text-left flex items-center justify-between gap-3"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="w-10 h-10 rounded-lg bg-surface border border-seam text-viridian flex items-center justify-center shrink-0">
                        <VolumeIcon className="w-5 h-5" />
                      </span>
                      <span className="font-bold text-ink text-base leading-snug">
                        {c.question}
                      </span>
                    </div>
                    <ChevronRightIcon className="w-5 h-5 text-viridian shrink-0" />
                  </button>
                </div>

                {isPrimed && (
                  <div className="px-4 pb-3.5 pt-1 flex justify-end">
                    <button
                      type="button"
                      onClick={() => onSelectCandidate(c.faq_id)}
                      aria-label={`${t(lang, "openAnswer")}: ${c.question}`}
                      className="min-h-[48px] px-5 py-2 rounded-lg bg-viridian text-white font-bold hover:bg-viridian-hover transition-colors"
                    >
                      {t(lang, "openAnswer")}
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
};
