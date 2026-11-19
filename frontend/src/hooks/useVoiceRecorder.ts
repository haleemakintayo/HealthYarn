import { useCallback, useEffect, useRef, useState } from "react";

export type MicErrorCode = "too_short" | "permission_denied" | "not_supported" | null;

const MIN_ASR_SECONDS = 2.2;
const WAV_TARGET_RATE = 16000;

export function encodeMonoWav(
  samples: Float32Array,
  sampleRate: number,
  minSeconds: number = MIN_ASR_SECONDS,
  targetRate: number = WAV_TARGET_RATE
): Blob {
  const resampledCount = Math.max(1, Math.round((samples.length / sampleRate) * targetRate));
  const totalFrames = Math.max(resampledCount, Math.ceil(minSeconds * targetRate));
  const buffer = new ArrayBuffer(44 + totalFrames * 2);
  const view = new DataView(buffer);

  const writeAscii = (offset: number, str: string) => {
    for (let i = 0; i < str.length; i += 1) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  };

  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + totalFrames * 2, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true); // PCM chunk size
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // Mono
  view.setUint32(24, targetRate, true);
  view.setUint32(28, targetRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(36, "data");
  view.setUint32(40, totalFrames * 2, true);

  const ratio = samples.length / resampledCount;
  for (let i = 0; i < resampledCount; i += 1) {
    const srcIdx = Math.min(samples.length - 1, Math.floor(i * ratio));
    const clamped = Math.max(-1, Math.min(1, samples[srcIdx] || 0));
    view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
  }
  // Trailing silence frames (>= 2.2s) remain 0-filled in the ArrayBuffer
  return new Blob([buffer], { type: "audio/wav" });
}

export async function padShortBlobToWav(
  blob: Blob,
  minSeconds: number = MIN_ASR_SECONDS
): Promise<{ blob: Blob; durationSeconds: number } | null> {
  if (typeof window === "undefined") return null;
  const AudioCtx =
    window.AudioContext ||
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtx || typeof blob.arrayBuffer !== "function") return null;

  let ctx: AudioContext | null = null;
  try {
    ctx = new AudioCtx();
    const raw = await blob.arrayBuffer();
    const decoded = await ctx.decodeAudioData(raw);
    const len = decoded.length;
    const chCount = Math.max(1, decoded.numberOfChannels);
    const mono = new Float32Array(len);
    for (let ch = 0; ch < chCount; ch += 1) {
      const data = decoded.getChannelData(ch);
      for (let i = 0; i < len; i += 1) {
        mono[i] += data[i] / chCount;
      }
    }
    const wavBlob = encodeMonoWav(mono, decoded.sampleRate, minSeconds, WAV_TARGET_RATE);
    const paddedDuration = Number(
      Math.max(decoded.duration, minSeconds).toFixed(2)
    );
    return { blob: wavBlob, durationSeconds: paddedDuration };
  } catch {
    return null;
  } finally {
    if (ctx) {
      ctx.close().catch(() => {});
    }
  }
}

function playTone(startHz: number, endHz: number) {
  try {
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(startHz, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(endHz, ctx.currentTime + 0.12);
    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.14);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.15);
    setTimeout(() => {
      ctx.close().catch(() => {});
    }, 250);
  } catch {
    // Web Audio API may be blocked or unsupported in tests
  }
}

export function useVoiceRecorder(
  onRecorded: (blob: Blob, durationSeconds: number) => void,
  maxSeconds: number = 15
) {
  const [isInitializing, setIsInitializing] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [micErrorCode, setMicErrorCode] = useState<MicErrorCode>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<number | null>(null);
  const isStartingRef = useRef(false);
  const pendingStopRef = useRef(false);
  const cancelledRef = useRef(false);
  const startedAtRef = useRef<number>(0);

  const cleanupTracks = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((tr) => tr.stop());
      streamRef.current = null;
    }
    recorderRef.current = null;
  }, []);

  const stopRecording = useCallback(() => {
    // If pointer was released while getUserMedia was still resolving, abort cleanly on arrival
    if (isStartingRef.current) {
      pendingStopRef.current = true;
      return;
    }
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") {
      cancelledRef.current = false;
      pendingStopRef.current = false;
      playTone(880, 587);
      try {
        if (typeof rec.requestData === "function" && rec.state === "recording") {
          rec.requestData();
        }
      } catch {
        // requestData may be unsupported on some mock/mobile implementations
      }
      rec.stop();
    }
    setIsRecording(false);
  }, []);

  const cancelRecording = useCallback(() => {
    cancelledRef.current = true;
    pendingStopRef.current = false;
    setIsInitializing(false);
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") {
      rec.stop();
    } else if (!isStartingRef.current) {
      cleanupTracks();
    }
    setIsRecording(false);
    setRecordingSeconds(0);
  }, [cleanupTracks]);

  const startRecording = useCallback(async () => {
    if (isStartingRef.current || recorderRef.current) {
      return;
    }
    setMicErrorCode(null);

    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setMicErrorCode("not_supported");
      return;
    }

    isStartingRef.current = true;
    pendingStopRef.current = false;
    cancelledRef.current = false;
    setIsInitializing(true);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      isStartingRef.current = false;
      setIsInitializing(false);

      if (cancelledRef.current) {
        stream.getTracks().forEach((tr) => tr.stop());
        return;
      }
      if (pendingStopRef.current) {
        stream.getTracks().forEach((tr) => tr.stop());
        pendingStopRef.current = false;
        setMicErrorCode("too_short");
        return;
      }

      streamRef.current = stream;
      chunksRef.current = [];

      const preferredTypes = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/ogg;codecs=opus",
        "audio/ogg",
        "audio/mp4"
      ];
      const mimeType = preferredTypes.find((m) => MediaRecorder.isTypeSupported?.(m)) || "";
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      recorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) {
          chunksRef.current.push(ev.data);
        }
      };

      recorder.onstop = async () => {
        const rawElapsed = (Date.now() - startedAtRef.current) / 1000;
        const elapsed = Math.min(maxSeconds, Math.max(0.2, rawElapsed));
        const chunks = [...chunksRef.current];
        const finalType = recorder.mimeType || mimeType || "audio/webm";
        chunksRef.current = [];
        cleanupTracks();
        setIsRecording(false);
        setRecordingSeconds(0);

        if (!cancelledRef.current) {
          const blob = new Blob(chunks, { type: finalType });
          if (chunks.length === 0 || blob.size === 0 || rawElapsed < 0.15) {
            setMicErrorCode("too_short");
            return;
          }
          const wavConverted = await padShortBlobToWav(blob, MIN_ASR_SECONDS);
          if (wavConverted) {
            onRecorded(wavConverted.blob, Math.min(maxSeconds, wavConverted.durationSeconds));
            return;
          }
          onRecorded(blob, Number(elapsed.toFixed(2)));
        }
      };

      startedAtRef.current = Date.now();
      setRecordingSeconds(0);
      setIsRecording(true);
      playTone(587, 880);
      recorder.start(250);
      recorderRef.current = recorder;

      timerRef.current = window.setInterval(() => {
        const secs = Math.floor((Date.now() - startedAtRef.current) / 1000);
        setRecordingSeconds(secs);
        if (secs >= maxSeconds) {
          stopRecording();
        }
      }, 250);
    } catch {
      isStartingRef.current = false;
      pendingStopRef.current = false;
      setIsInitializing(false);
      cleanupTracks();
      setIsRecording(false);
      setMicErrorCode("permission_denied");
    }
  }, [cleanupTracks, maxSeconds, onRecorded, stopRecording]);

  useEffect(() => {
    return () => {
      cancelledRef.current = true;
      cleanupTracks();
    };
  }, [cleanupTracks]);

  return {
    isInitializing,
    isRecording,
    recordingSeconds,
    micErrorCode,
    startRecording,
    stopRecording,
    cancelRecording
  };
}
