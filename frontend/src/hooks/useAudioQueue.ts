import { useCallback, useEffect, useRef, useState } from "react";
import { fetchTtsAudio } from "../services/api";
import type { Lang } from "../types";

const SPEECH_LOCALE: Record<Lang, string> = {
  en: "en-NG",
  pcm: "en-NG",
  yo: "yo-NG"
};

export interface PlayAnswerOrSpeakArgs {
  clipUrl: string | null | undefined;
  text: string;
  lang: Lang;
  disclaimerUrl?: string | null;
}

export function useAudioQueue() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const queueRef = useRef<string[]>([]);
  const blobUrlRef = useRef<string | null>(null);
  const speakRequestIdRef = useRef<number>(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);
  const [audioNotice, setAudioNotice] = useState<string | null>(null);
  const [activeStage, setActiveStage] = useState<number>(0);
  const [playbackRate, setPlaybackRate] = useState<number>(1.0);

  const stop = useCallback(() => {
    speakRequestIdRef.current += 1;
    queueRef.current = [];
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.onended = null;
      audioRef.current.onerror = null;
      audioRef.current = null;
    }
    if (blobUrlRef.current) {
      if (typeof URL !== "undefined" && typeof URL.revokeObjectURL === "function") {
        URL.revokeObjectURL(blobUrlRef.current);
      }
      blobUrlRef.current = null;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsLoadingAudio(false);
    setAudioNotice(null);
    setIsPlaying(false);
    setActiveStage(0);
  }, []);

  const playNext = useCallback(
    (rate: number) => {
      const nextUrl = queueRef.current.shift();
      if (!nextUrl) {
        setIsPlaying(false);
        return;
      }

      if (typeof Audio === "undefined") {
        setIsPlaying(false);
        return;
      }

      try {
        const audio = new Audio(nextUrl);
        audio.playbackRate = rate;
        audioRef.current = audio;
        setIsPlaying(true);

        audio.onended = () => {
          setActiveStage((s) => s + 1);
          playNext(rate);
        };
        audio.onerror = () => {
          setActiveStage((s) => s + 1);
          playNext(rate);
        };

        const maybePromise = audio.play();
        if (maybePromise && typeof maybePromise.catch === "function") {
          maybePromise.catch(() => {
            setIsPlaying(false);
          });
        }
      } catch {
        setIsPlaying(false);
      }
    },
    []
  );

  const playSequence = useCallback(
    (urls: Array<string | null | undefined>, rateOverride?: number) => {
      stop();
      const valid = urls.filter((u): u is string => Boolean(u));
      if (valid.length === 0) {
        return;
      }
      queueRef.current = [...valid];
      setActiveStage(0);
      playNext(rateOverride ?? playbackRate);
    },
    [playNext, playbackRate, stop]
  );

  const playAnswerOrSpeak = useCallback(
    async ({ clipUrl, text, lang, disclaimerUrl }: PlayAnswerOrSpeakArgs) => {
      if (clipUrl) {
        playSequence([clipUrl, disclaimerUrl]);
        return;
      }

      stop();
      const requestId = speakRequestIdRef.current;
      const trimmed = text.trim();
      if (!trimmed) {
        if (disclaimerUrl) {
          playSequence([disclaimerUrl]);
        }
        return;
      }

      setIsLoadingAudio(true);
      setIsPlaying(false);
      setAudioNotice(null);
      setActiveStage(0);

      try {
        const blob = await fetchTtsAudio(trimmed, lang);
        if (speakRequestIdRef.current !== requestId) {
          return;
        }
        if (!blob || blob.size === 0) {
          throw new Error("Empty TTS audio");
        }
        if (typeof URL === "undefined" || typeof URL.createObjectURL !== "function") {
          throw new Error("Object URL unsupported");
        }
        const objectUrl = URL.createObjectURL(blob);
        blobUrlRef.current = objectUrl;
        setIsLoadingAudio(false);
        const queue = [objectUrl, ...(disclaimerUrl ? [disclaimerUrl] : [])];
        queueRef.current = queue;
        playNext(playbackRate);
        return;
      } catch {
        if (speakRequestIdRef.current !== requestId) {
          return;
        }
        setIsLoadingAudio(false);
      }

      if (
        typeof window !== "undefined" &&
        "speechSynthesis" in window &&
        window.speechSynthesis &&
        typeof SpeechSynthesisUtterance !== "undefined"
      ) {
        let yoVoice: SpeechSynthesisVoice | undefined;
        if (lang === "yo") {
          const voices =
            typeof window.speechSynthesis.getVoices === "function"
              ? window.speechSynthesis.getVoices()
              : [];
          yoVoice = voices.find((v) => v.lang?.toLowerCase().startsWith("yo"));
          if (!yoVoice) {
            setIsPlaying(false);
            setActiveStage(0);
            setAudioNotice("liveAudioUnavailable");
            return;
          }
        }
        try {
          const utterance = new SpeechSynthesisUtterance(trimmed);
          utterance.lang = yoVoice?.lang || SPEECH_LOCALE[lang] || "en-NG";
          if (yoVoice) {
            utterance.voice = yoVoice;
          }
          utterance.rate = playbackRate;
          setIsPlaying(true);
          utterance.onend = () => {
            if (speakRequestIdRef.current !== requestId) return;
            if (disclaimerUrl) {
              queueRef.current = [disclaimerUrl];
              setActiveStage(1);
              playNext(playbackRate);
            } else {
              setIsPlaying(false);
              setActiveStage(0);
            }
          };
          utterance.onerror = () => {
            if (speakRequestIdRef.current !== requestId) return;
            setIsPlaying(false);
            setActiveStage(0);
          };
          window.speechSynthesis.speak(utterance);
          return;
        } catch {
          // Fall through cleanly if browser blocks speechSynthesis
        }
      }

      if (disclaimerUrl && lang !== "yo") {
        playSequence([disclaimerUrl]);
      } else {
        setIsPlaying(false);
        setActiveStage(0);
        if (lang === "yo") {
          setAudioNotice("liveAudioUnavailable");
        }
      }
    },
    [playNext, playSequence, playbackRate, stop]
  );

  const toggleSpeed = useCallback(() => {
    setPlaybackRate((prev) => {
      const next = prev === 1.0 ? 0.75 : 1.0;
      if (audioRef.current) {
        audioRef.current.playbackRate = next;
      }
      return next;
    });
  }, []);

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return {
    isPlaying,
    isLoadingAudio,
    audioNotice,
    activeStage,
    playbackRate,
    playSequence,
    playAnswerOrSpeak,
    stop,
    toggleSpeed
  };
}
