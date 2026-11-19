import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { t } from "../i18n";
import type { Lang, QuestionSummary, TopicSummary } from "../types";
import {
  ChevronRightIcon,
  KeyboardIcon,
  MicIcon,
  TopicIcon,
  VolumeIcon,
  WifiOffIcon
} from "./Icons";

interface HomeViewProps {
  lang: Lang;
  topics: TopicSummary[];
  loading: boolean;
  isOffline: boolean;
  isInitializing?: boolean;
  isRecording: boolean;
  recordingSeconds: number;
  isSubmittingVoice: boolean;
  voiceError: string | null;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onCancelRecording: () => void;
  onSubmitTypedText?: (text: string) => void;
  onSelectTopic: (slug: string) => void;
  onOpenQuestion?: (faqId: number) => void;
  onPlayClip?: (url: string | null | undefined) => void;
}

export const HomeView: React.FC<HomeViewProps> = ({
  lang,
  topics,
  loading,
  isOffline,
  isInitializing = false,
  isRecording,
  recordingSeconds,
  isSubmittingVoice,
  voiceError,
  onStartRecording,
  onStopRecording,
  onCancelRecording,
  onSubmitTypedText,
  onSelectTopic,
  onOpenQuestion,
  onPlayClip
}) => {
  const [tapMode, setTapMode] = useState(true);
  const [showTypedInput, setShowTypedInput] = useState(false);
  const [holdingGesture, setHoldingGesture] = useState(false);
  const [typedQuery, setTypedQuery] = useState("");
  const holdingRef = useRef(false);

  const remaining = Math.max(0, 15 - recordingSeconds);
  const activeVoiceCapture = isRecording || isInitializing;

  // Pick up to 3 representative starter questions across topics for progressive onboarding
  const starterQuestions = useMemo<QuestionSummary[]>(() => {
    const picks: QuestionSummary[] = [];
    for (const tp of topics) {
      if (tp.questions.length > 0) {
        picks.push(tp.questions[0]);
      }
      if (picks.length >= 3) break;
    }
    return picks;
  }, [topics]);

  const finishHold = useCallback(() => {
    if (!holdingRef.current) return;
    holdingRef.current = false;
    setHoldingGesture(false);
    onStopRecording();
  }, [onStopRecording]);

  const abortHold = useCallback(() => {
    if (!holdingRef.current) return;
    holdingRef.current = false;
    setHoldingGesture(false);
    onCancelRecording();
  }, [onCancelRecording]);

  // Listen at window level while holding so releasing outside the mic circle still sends cleanly
  useEffect(() => {
    if (!holdingGesture) return;
    const handlePointerUp = () => finishHold();
    const handlePointerCancel = () => abortHold();
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerCancel);
    window.addEventListener("blur", handlePointerCancel);
    return () => {
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerCancel);
      window.removeEventListener("blur", handlePointerCancel);
    };
  }, [abortHold, finishHold, holdingGesture]);

  const handleMicTap = () => {
    if (isOffline || isSubmittingVoice) return;
    if (activeVoiceCapture) {
      onStopRecording();
    } else {
      onStartRecording();
    }
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (tapMode || isOffline || isSubmittingVoice || activeVoiceCapture) return;
    if (e.button !== undefined && e.button !== 0 && e.pointerType === "mouse") return;
    holdingRef.current = true;
    setHoldingGesture(true);
    try {
      e.currentTarget.setPointerCapture?.(e.pointerId);
    } catch {
      // Ignore synthetic PointerEvents without active pointerId
    }
    onStartRecording();
  };

  const handlePointerUp = (e: React.PointerEvent<HTMLButtonElement>) => {
    if (tapMode) return;
    try {
      if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
        e.currentTarget.releasePointerCapture(e.pointerId);
      }
    } catch {
      // Ignore
    }
    finishHold();
  };

  return (
    <main className="max-w-2xl mx-auto px-4 py-5">
      <section
        aria-labelledby="voice-triage-heading"
        className="bg-surface border border-seam rounded-2xl p-6 sm:p-7 text-center shadow-sm mb-7"
      >
        <h1 id="voice-triage-heading" className="text-xl sm:text-2xl font-bold text-ink mb-1.5">
          {t(lang, "heroPrimaryBtn")}
        </h1>
        <p className="text-sm text-ink-muted prose-measure mx-auto mb-5" aria-live="polite">
          {tapMode ? t(lang, "tapVoiceHelper") : t(lang, "holdTooShort")}
        </p>

        {isOffline ? (
          <div className="py-4 flex flex-col items-center gap-3">
            <div className="w-20 h-20 rounded-full bg-ochre-bg border border-ochre-border text-ochre flex items-center justify-center">
              <WifiOffIcon className="w-9 h-9" />
            </div>
            <p className="text-lg font-bold text-ink max-w-sm">
              {t(lang, "micNeedsInternet")}
            </p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            {/* Keep a single mic button mounted across idle & recording so pointerup never drops mid-hold */}
            <button
              type="button"
              disabled={isSubmittingVoice}
              aria-pressed={activeVoiceCapture}
              onPointerDown={handlePointerDown}
              onPointerUp={handlePointerUp}
              onPointerCancel={!tapMode ? abortHold : undefined}
              onContextMenu={(e) => {
                if (!tapMode) e.preventDefault();
              }}
              onClick={tapMode ? handleMicTap : undefined}
              onKeyDown={(e) => {
                if (!tapMode && !e.repeat && (e.key === " " || e.key === "Enter")) {
                  e.preventDefault();
                  handleMicTap();
                }
              }}
              aria-label={
                isRecording
                  ? t(lang, "tapToStop")
                  : tapMode
                  ? t(lang, "tapToStart")
                  : t(lang, "holdToSpeak")
              }
              className={`w-36 h-36 rounded-full flex flex-col items-center justify-center gap-1.5 disabled:opacity-60 select-none touch-none transition-all ${
                isRecording
                  ? "bg-hy-amber/25 text-hy-ink border-2 border-hy-amber animate-pulse scale-105 shadow-lg"
                  : isInitializing
                  ? "bg-hy-amber/60 text-hy-ink border-2 border-hy-amber shadow-md"
                  : "bg-hy-amber text-hy-ink border-2 border-hy-ink/10 shadow-md hover:bg-amber-hover active:scale-95"
              }`}
            >
              <MicIcon className={isRecording ? "w-10 h-10" : "w-11 h-11"} />
              {isRecording ? (
                <span className="text-2xl font-bold text-hy-ink tabular-nums leading-none">
                  {remaining}s
                </span>
              ) : (
                <span className="text-xs font-extrabold px-3 leading-tight">
                  {isSubmittingVoice
                    ? t(lang, "processingVoice")
                    : isInitializing
                    ? t(lang, "preparingMic")
                    : tapMode
                    ? t(lang, "tapToStart")
                    : t(lang, "holdToSpeak")}
                </span>
              )}
            </button>

            {activeVoiceCapture ? (
              <div className="flex flex-col items-center gap-3" role="status" aria-live="polite">
                <div>
                  <h2 className="text-xl font-bold text-ink">
                    {isInitializing ? t(lang, "preparingMic") : t(lang, "listeningTitle")}
                  </h2>
                  <p className="text-sm text-ink-muted mt-1">
                    {!tapMode && holdingGesture ? t(lang, "releaseToSend") : t(lang, "listeningHint")}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {(tapMode || !holdingGesture) && (
                    <button
                      type="button"
                      onClick={onStopRecording}
                      aria-label={t(lang, "tapToStop")}
                      className="min-h-[52px] px-6 py-3 rounded-full bg-viridian text-white font-bold hover:bg-viridian-hover transition-colors"
                    >
                      {t(lang, "tapToStop")}
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      holdingRef.current = false;
                      setHoldingGesture(false);
                      onCancelRecording();
                    }}
                    aria-label={t(lang, "cancel")}
                    className="min-h-[52px] px-5 py-3 rounded-full bg-ground border border-seam text-ink font-semibold hover:bg-subtle transition-colors"
                  >
                    {t(lang, "cancel")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={() => setTapMode((v) => !v)}
                  aria-label={tapMode ? t(lang, "switchHoldMode") : t(lang, "switchTapMode")}
                  className="min-h-[48px] px-3.5 py-2 rounded-lg text-sm font-semibold text-viridian hover:bg-viridian-soft transition-colors"
                >
                  {tapMode ? t(lang, "switchHoldMode") : t(lang, "switchTapMode")}
                </button>
                {onSubmitTypedText && (
                  <button
                    type="button"
                    aria-expanded={showTypedInput}
                    aria-controls="typed-question-panel"
                    onClick={() => setShowTypedInput((v) => !v)}
                    className="min-h-[48px] px-3.5 py-2 rounded-lg text-sm font-semibold text-ink hover:bg-subtle border border-seam inline-flex items-center gap-1.5 transition-colors"
                  >
                    <KeyboardIcon className="w-4 h-4 text-viridian" />
                    <span>
                      {showTypedInput ? t(lang, "hideTypedQuestion") : t(lang, "typeQuestionToggle")}
                    </span>
                  </button>
                )}
              </div>
            )}

            {voiceError && !activeVoiceCapture && (
              <div
                role="alert"
                className="w-full text-left bg-ochre-bg border border-ochre-border text-ochre rounded-xl p-4 text-sm font-medium"
              >
                {voiceError}
              </div>
            )}

            {onSubmitTypedText && !activeVoiceCapture && showTypedInput && (
              <form
                id="typed-question-panel"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (typedQuery.trim()) {
                    onSubmitTypedText(typedQuery.trim());
                    setTypedQuery("");
                  }
                }}
                className="w-full pt-4 border-t border-seam flex items-center gap-2"
              >
                <input
                  type="text"
                  value={typedQuery}
                  onChange={(e) => setTypedQuery(e.target.value)}
                  placeholder={t(lang, "tryTypedQuestion")}
                  aria-label={t(lang, "tryTypedQuestion")}
                  className="flex-1 min-h-[48px] px-3.5 py-2 rounded-lg bg-ground border border-seam text-ink text-base placeholder:text-ink-muted"
                />
                <button
                  type="submit"
                  disabled={isSubmittingVoice || !typedQuery.trim()}
                  aria-label={t(lang, "sendTypedQuestion")}
                  className="min-h-[48px] px-4 py-2 rounded-lg bg-viridian text-white font-semibold hover:bg-viridian-hover disabled:opacity-50 transition-colors"
                >
                  {t(lang, "sendTypedQuestion")}
                </button>
              </form>
            )}

            {!activeVoiceCapture && starterQuestions.length > 0 && (
              <div className="w-full pt-4 border-t border-seam text-left">
                <p className="text-sm font-bold text-ink mb-2.5">{t(lang, "tryAskingHeading")}</p>
                <div className="flex flex-col gap-2">
                  {starterQuestions.map((q) => (
                    <div
                      key={q.faq_id}
                      className="bg-ground border border-seam rounded-xl flex items-stretch overflow-hidden hover:border-viridian transition-colors"
                    >
                      {q.question_audio_url && onPlayClip && (
                        <button
                          type="button"
                          onClick={() => onPlayClip(q.question_audio_url)}
                          aria-label={`${t(lang, "playQuestionAudio")}: ${q.question}`}
                          className="min-w-[48px] min-h-[48px] px-3 bg-viridian-soft text-viridian hover:bg-viridian hover:text-white flex items-center justify-center border-r border-seam transition-colors shrink-0"
                        >
                          <VolumeIcon className="w-5 h-5" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() =>
                          onOpenQuestion
                            ? onOpenQuestion(q.faq_id)
                            : onSubmitTypedText?.(q.question)
                        }
                        className="flex-1 min-h-[48px] px-3.5 py-2.5 text-left text-sm font-semibold text-ink flex items-center justify-between gap-2"
                      >
                        <span className="leading-snug">{q.question}</span>
                        <ChevronRightIcon className="w-4 h-4 text-viridian shrink-0" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      <section aria-labelledby="topics-heading">
        <h2 id="topics-heading" className="text-xl font-bold text-ink mt-2 mb-4">
          {t(lang, "topicsHeading")}
        </h2>

        {loading && topics.length === 0 ? (
          <div className="space-y-3" aria-busy="true" aria-label={t(lang, "loading")}>
            {[1, 2, 3, 4, 5].map((idx) => (
              <div
                key={idx}
                className="h-20 rounded-xl bg-subtle border border-seam animate-pulse"
              />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {topics.map((topic) => (
              <button
                key={topic.slug}
                type="button"
                onClick={() => onSelectTopic(topic.slug)}
                aria-label={`${topic.name} (${topic.questions.length} ${t(lang, "questionsCount")})`}
                className="w-full min-h-[72px] bg-surface border border-seam rounded-xl px-4 py-3.5 text-left flex items-center justify-between gap-4 hover:border-viridian hover:bg-viridian-soft/40 transition-colors"
              >
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="w-12 h-12 rounded-card bg-hy-sand flex items-center justify-center shrink-0">
                    <TopicIcon icon={topic.icon} className="w-7 h-7" />
                  </div>
                  <div className="min-w-0">
                    <div className="text-lg font-bold text-ink leading-snug">{topic.name}</div>
                    <div className="text-sm text-ink-muted tabular-nums">
                      {topic.questions.length} {t(lang, "questionsCount")}
                    </div>
                  </div>
                </div>
                <ChevronRightIcon className="w-6 h-6 text-ink-muted shrink-0" />
              </button>
            ))}
          </div>
        )}
      </section>
    </main>
  );
};
