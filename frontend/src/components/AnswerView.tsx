import React, { useEffect, useRef, useState } from "react";
import { t } from "../i18n";
import type { AnswerPayload, Clinic, Lang } from "../types";
import {
  ArrowLeftIcon,
  ChevronRightIcon,
  ClipboardCheckIcon,
  HelpCircleIcon,
  MapPinIcon,
  PhoneIcon,
  PlayIcon,
  ShareIcon,
  StopIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
  VolumeIcon
} from "./Icons";

interface AnswerViewProps {
  lang: Lang;
  answer: AnswerPayload;
  autoplayEnabled: boolean;
  isPlaying: boolean;
  isLoadingAudio?: boolean;
  audioNotice?: string | null;
  activeAudioStage?: number;
  playbackRate: number;
  clinics?: Clinic[];
  onPlayAnswerSequence: (
    answerUrl: string | null,
    disclaimerUrl: string | null,
    spokenText: string
  ) => void;
  onStopAudio?: () => void;
  onToggleSpeed: () => void;
  onFeedback: (rating: 1 | -1) => Promise<void>;
  onBrowseTopic?: (slug: string) => void;
  onResetHome: () => void;
}

export const AnswerView: React.FC<AnswerViewProps> = ({
  lang,
  answer,
  autoplayEnabled,
  isPlaying,
  isLoadingAudio = false,
  audioNotice = null,
  activeAudioStage = 0,
  playbackRate,
  clinics = [],
  onPlayAnswerSequence,
  onStopAudio,
  onToggleSpeed,
  onFeedback,
  onBrowseTopic,
  onResetHome
}) => {
  const initialTrack = answer.diagnosis_status === "diagnosed" ? "diagnosed" : "undiagnosed";
  const [activeTrack, setActiveTrack] = useState<"undiagnosed" | "diagnosed">(initialTrack);
  const [rated, setRated] = useState<1 | -1 | null>(null);
  const [shareNote, setShareNote] = useState<string>("");
  const [showClinics, setShowClinics] = useState<boolean>(Boolean(answer.suggest_clinics));
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
    setShowClinics(Boolean(answer.suggest_clinics));
  }, [answer.faq_id, answer.question, answer.lang, answer.suggest_clinics]);

  const hasDualTracks = Boolean(
    answer.undiagnosed_text ||
      answer.diagnosed_text ||
      answer.undiagnosed_audio_url ||
      answer.diagnosed_audio_url
  );

  const displayedAnswerText =
    activeTrack === "diagnosed"
      ? answer.diagnosed_text || answer.answer_text
      : answer.undiagnosed_text || answer.answer_text;

  const activeAudioUrl =
    activeTrack === "diagnosed"
      ? answer.diagnosed_audio_url || answer.answer_audio_url
      : answer.undiagnosed_audio_url || answer.answer_audio_url;

  useEffect(() => {
    const nextInitial = answer.diagnosis_status === "diagnosed" ? "diagnosed" : "undiagnosed";
    setActiveTrack(nextInitial);
    setRated(null);
    setShareNote("");
    if (autoplayEnabled) {
      const nextAudioUrl =
        nextInitial === "diagnosed"
          ? answer.diagnosed_audio_url || answer.answer_audio_url
          : answer.undiagnosed_audio_url || answer.answer_audio_url;
      const nextSpokenText =
        nextInitial === "diagnosed"
          ? answer.diagnosed_text || answer.answer_text
          : answer.undiagnosed_text || answer.answer_text;
      onPlayAnswerSequence(nextAudioUrl, answer.disclaimer_audio_url ?? null, nextSpokenText);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answer.faq_id, answer.question, answer.lang, answer.diagnosis_status]);

  const handleSelectTrack = (nextTrack: "undiagnosed" | "diagnosed") => {
    setActiveTrack(nextTrack);
    const nextAudioUrl =
      nextTrack === "diagnosed"
        ? answer.diagnosed_audio_url || answer.answer_audio_url
        : answer.undiagnosed_audio_url || answer.answer_audio_url;
    const nextSpokenText =
      nextTrack === "diagnosed"
        ? answer.diagnosed_text || answer.answer_text
        : answer.undiagnosed_text || answer.answer_text;
    if (autoplayEnabled || isPlaying) {
      onPlayAnswerSequence(nextAudioUrl, answer.disclaimer_audio_url ?? null, nextSpokenText);
    }
  };

  const handleFeedback = async (rating: 1 | -1) => {
    if (rated !== null) return;
    setRated(rating);
    await onFeedback(rating);
  };

  const handleShare = async () => {
    const textBody = `${answer.question}\n\n${displayedAnswerText}\n\n${answer.disclaimer_text || ""}`;
    try {
      if (typeof navigator !== "undefined" && navigator.share) {
        if (activeAudioUrl && typeof fetch !== "undefined") {
          try {
            const resp = await fetch(activeAudioUrl);
            const blob = await resp.blob();
            const ext = activeAudioUrl.endsWith(".wav") ? "wav" : "ogg";
            const file = new File([blob], `${answer.intent_key}.${ext}`, {
              type: blob.type || "audio/ogg"
            });
            if (navigator.canShare && navigator.canShare({ files: [file] })) {
              await navigator.share({
                title: answer.question,
                text: textBody,
                files: [file]
              });
              return;
            }
          } catch {
            // Fall through to text share
          }
        }
        await navigator.share({
          title: answer.question,
          text: textBody
        });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(textBody);
        setShareNote("Copied to clipboard");
      }
    } catch {
      // User cancelled share dialog
    }
  };

  return (
    <main className="max-w-2xl mx-auto px-4 py-5">
      <button
        type="button"
        onClick={onResetHome}
        aria-label={t(lang, "notWhatIAsked")}
        className="min-h-[48px] px-4 py-2 rounded-lg bg-surface border border-seam text-ink font-semibold inline-flex items-center gap-2 hover:bg-subtle transition-colors mb-5"
      >
        <ArrowLeftIcon className="w-5 h-5 text-viridian" />
        <span>{t(lang, "notWhatIAsked")}</span>
      </button>

      <article className="bg-surface border border-seam rounded-xl p-6 sm:p-7 shadow-sm">
        <div className="mb-3">
          {answer.answer_source === "ai_guardrailed" ? (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300">
              {t(lang, "sourceBadgeAiGuardrailed")}
            </span>
          ) : (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-viridian-soft text-viridian border border-viridian/25">
              {t(lang, "sourceBadgeVerified")}
            </span>
          )}
        </div>

        <h1
          ref={headingRef}
          tabIndex={-1}
          className="text-xl sm:text-2xl font-bold text-ink leading-snug mb-5 focus:outline-none"
        >
          {answer.question}
        </h1>

        {hasDualTracks && (
          <div className="mb-5">
            <p className="text-sm font-bold text-ink mb-2">
              {t(lang, "diagnosisToggleLabel")}
            </p>
            <div
              role="group"
              aria-label={t(lang, "diagnosisToggleLabel")}
              className="bg-subtle p-1 rounded-xl border border-seam grid grid-cols-1 sm:grid-cols-2 gap-1.5"
            >
              <button
                type="button"
                aria-pressed={activeTrack === "undiagnosed"}
                onClick={() => handleSelectTrack("undiagnosed")}
                className={`min-h-[48px] px-3.5 py-2.5 rounded-lg text-sm font-semibold transition-colors inline-flex items-center justify-center gap-2 text-center ${
                  activeTrack === "undiagnosed"
                    ? "bg-viridian text-white shadow-sm"
                    : "bg-transparent text-ink hover:bg-surface"
                }`}
              >
                <HelpCircleIcon className="w-4 h-4 shrink-0" />
                <span>{t(lang, "undiagnosedTab")}</span>
              </button>
              <button
                type="button"
                aria-pressed={activeTrack === "diagnosed"}
                onClick={() => handleSelectTrack("diagnosed")}
                className={`min-h-[48px] px-3.5 py-2.5 rounded-lg text-sm font-semibold transition-colors inline-flex items-center justify-center gap-2 text-center ${
                  activeTrack === "diagnosed"
                    ? "bg-viridian text-white shadow-sm"
                    : "bg-transparent text-ink hover:bg-surface"
                }`}
              >
                <ClipboardCheckIcon className="w-4 h-4 shrink-0" />
                <span>{t(lang, "diagnosedTab")}</span>
              </button>
            </div>
            {(answer.diagnosis_status === "diagnosed" || answer.diagnosis_status === "undiagnosed") && (
              <p className="text-xs font-medium text-viridian mt-2">
                {t(lang, "diagnosisAutoDetectedHint")}
              </p>
            )}
          </div>
        )}

        <div className="bg-ground border border-seam rounded-xl p-3.5 mb-6">
          <div className="flex flex-wrap items-center gap-2.5">
            {(isPlaying || isLoadingAudio) && onStopAudio ? (
              <button
                type="button"
                onClick={onStopAudio}
                aria-label={t(lang, "stopAudio")}
                className="min-h-[48px] px-4 py-2.5 rounded-lg bg-viridian text-white font-semibold inline-flex items-center gap-2 hover:bg-viridian-hover transition-colors"
              >
                <StopIcon className="w-5 h-5" />
                <span>{t(lang, "stopAudio")}</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={() =>
                  onPlayAnswerSequence(
                    activeAudioUrl,
                    answer.disclaimer_audio_url ?? null,
                    displayedAnswerText
                  )
                }
                aria-label={t(lang, "listenAnswer")}
                className="min-h-[48px] px-4 py-2.5 rounded-lg bg-viridian text-white font-semibold inline-flex items-center gap-2 hover:bg-viridian-hover transition-colors"
              >
                <PlayIcon className="w-5 h-5" />
                <span>{t(lang, "listenAnswer")}</span>
              </button>
            )}

            <button
              type="button"
              onClick={onToggleSpeed}
              aria-label={playbackRate === 1.0 ? t(lang, "slowSpeed") : t(lang, "normalSpeed")}
              className={`min-h-[48px] px-4 py-2.5 rounded-lg border font-semibold tabular-nums transition-colors ${
                playbackRate === 0.75
                  ? "bg-viridian-soft border-viridian text-viridian"
                  : "bg-surface border-seam text-ink hover:bg-subtle"
              }`}
            >
              {playbackRate === 0.75 ? t(lang, "slowSpeed") : t(lang, "normalSpeed")}
            </button>

            <button
              type="button"
              onClick={handleShare}
              aria-label={t(lang, "shareAnswer")}
              className="min-h-[48px] px-4 py-2.5 rounded-lg bg-surface border border-seam text-ink font-semibold inline-flex items-center gap-2 hover:bg-subtle transition-colors"
            >
              <ShareIcon className="w-5 h-5 text-viridian" />
              <span>{t(lang, "shareAnswer")}</span>
            </button>
          </div>

          {(isLoadingAudio || isPlaying) && (
            <p
              className="mt-2.5 text-xs font-semibold text-viridian inline-flex items-center gap-1.5"
              role="status"
              aria-live="polite"
            >
              <VolumeIcon className="w-4 h-4 shrink-0" />
              <span>
                {isLoadingAudio
                  ? t(lang, "preparingVoice")
                  : activeAudioStage === 0
                    ? t(lang, "speakingAnswer")
                    : t(lang, "speakingDisclaimer")}
              </span>
            </p>
          )}

          {!isLoadingAudio && !isPlaying && audioNotice && (
            <p
              className="mt-2.5 text-xs font-medium text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2"
              role="status"
              aria-live="polite"
            >
              {t(lang, audioNotice as "liveAudioUnavailable")}
            </p>
          )}
        </div>

        {shareNote && (
          <p className="text-sm text-viridian font-medium mb-4" role="status">
            {shareNote}
          </p>
        )}

        <p className="text-lg text-ink leading-relaxed prose-measure mb-6">
          {displayedAnswerText}
        </p>

        {answer.disclaimer_text && (
          <section
            aria-label={t(lang, "disclaimerLabel")}
            className="bg-subtle border border-seam rounded-lg p-4 mb-5"
          >
            <p className="text-sm font-bold text-ink mb-1">{t(lang, "disclaimerLabel")}</p>
            <p className="text-sm text-ink-muted prose-measure">{answer.disclaimer_text}</p>
          </section>
        )}

        {answer.source_reference && (
          <p className="text-xs text-ink-muted mb-6">
            <span className="font-semibold">{t(lang, "sourceLabel")}: </span>
            {answer.source_reference}
          </p>
        )}

        <div className="pt-5 border-t border-seam flex flex-wrap items-center justify-between gap-4">
          <span className="text-base font-semibold text-ink">
            {rated === null ? t(lang, "wasThisHelpful") : t(lang, "thanksFeedback")}
          </span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              disabled={rated !== null}
              onClick={() => handleFeedback(1)}
              aria-label={t(lang, "helpfulYes")}
              className={`min-h-[48px] min-w-[48px] px-4 py-2 rounded-lg border font-semibold inline-flex items-center gap-2 transition-colors ${
                rated === 1
                  ? "bg-viridian text-white border-viridian"
                  : "bg-ground border-seam text-ink hover:bg-viridian-soft disabled:opacity-60"
              }`}
            >
              <ThumbsUpIcon className="w-5 h-5" />
              <span>{t(lang, "helpfulYes")}</span>
            </button>

            <button
              type="button"
              disabled={rated !== null}
              onClick={() => handleFeedback(-1)}
              aria-label={t(lang, "helpfulNo")}
              className={`min-h-[48px] min-w-[48px] px-4 py-2 rounded-lg border font-semibold inline-flex items-center gap-2 transition-colors ${
                rated === -1
                  ? "bg-ochre text-white border-ochre"
                  : "bg-ground border-seam text-ink hover:bg-subtle disabled:opacity-60"
              }`}
            >
              <ThumbsDownIcon className="w-5 h-5" />
              <span>{t(lang, "helpfulNo")}</span>
            </button>
          </div>
        </div>

        <section
          aria-labelledby="next-steps-heading"
          className="mt-6 pt-5 border-t border-seam"
        >
          <h2 id="next-steps-heading" className="text-base font-bold text-ink mb-3">
            {t(lang, "nextStepsHeading")}
          </h2>
          <div className="flex flex-wrap gap-2.5">
            {clinics.length > 0 && (
              <button
                type="button"
                aria-expanded={showClinics}
                aria-controls="answer-clinics-panel"
                onClick={() => setShowClinics((prev) => !prev)}
                className={`min-h-[48px] px-4 py-2.5 rounded-lg border font-semibold inline-flex items-center gap-2 transition-colors ${
                  showClinics
                    ? "bg-viridian-soft border-viridian text-viridian"
                    : "bg-ground border-seam text-ink hover:bg-subtle"
                }`}
              >
                <MapPinIcon className="w-5 h-5 text-viridian shrink-0" />
                <span>
                  {showClinics ? t(lang, "hideNearbyClinics") : t(lang, "nearbyClinicsBtn")}
                </span>
              </button>
            )}

            {answer.topic_slug && onBrowseTopic && (
              <button
                type="button"
                onClick={() => onBrowseTopic(answer.topic_slug!)}
                className="min-h-[48px] px-4 py-2.5 rounded-lg bg-ground border border-seam text-ink font-semibold inline-flex items-center gap-1.5 hover:bg-subtle transition-colors"
              >
                <span>{answer.topic_name || t(lang, "moreInTopicBtn")}</span>
                <ChevronRightIcon className="w-4 h-4 text-viridian" />
              </button>
            )}

            <button
              type="button"
              onClick={onResetHome}
              className="min-h-[48px] px-4 py-2.5 rounded-lg bg-ground border border-seam text-ink font-semibold inline-flex items-center gap-2 hover:bg-subtle transition-colors"
            >
              <span>{t(lang, "askAnotherBtn")}</span>
            </button>
          </div>

          {showClinics && clinics.length > 0 && (
            <div id="answer-clinics-panel" className="mt-4 pt-4 border-t border-seam">
              <p className="text-sm font-medium text-ink-muted mb-3">
                {t(lang, "nearbyClinicsNote")}
              </p>
              <ul className="space-y-2.5">
                {clinics.map((clinic) => (
                  <li
                    key={clinic.id}
                    className="bg-ground border border-seam rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-2.5"
                  >
                    <div>
                      <div className="font-bold text-ink text-sm sm:text-base">{clinic.name}</div>
                      <div className="text-xs sm:text-sm text-ink-muted">
                        {clinic.type} · {clinic.lga}, {clinic.state}
                      </div>
                    </div>
                    <a
                      href={`tel:${clinic.phone}`}
                      aria-label={`${t(lang, "redFlagCallBtn")} ${clinic.name}`}
                      className="min-h-[44px] px-3.5 py-2 rounded-lg bg-surface border border-seam text-viridian font-bold text-sm inline-flex items-center gap-1.5 hover:bg-viridian-soft transition-colors tabular-nums"
                    >
                      <PhoneIcon className="w-4 h-4 shrink-0" />
                      <span>{clinic.phone}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </article>
    </main>
  );
};
