import type {
  AnswerPayload,
  AskResponse,
  BundleResponse,
  Clinic,
  Lang,
  TopicSummary
} from "../types";

export interface MetaResponse {
  demo_mode: boolean;
  content_reviewed?: boolean;
  content_last_updated: string;
  clinical_reviewers: string;
  language_reviewers: string;
  welcome_audio?: Partial<Record<Lang, string | null>>;
  consent_audio?: Partial<Record<Lang, string | null>>;
  hero_audio?: Partial<Record<Lang, string | null>>;
  sample_audio?: Partial<Record<Lang, string | null>>;
}

export async function fetchMeta(): Promise<MetaResponse> {
  const res = await fetch("/api/meta");
  if (!res.ok) {
    throw new Error("Failed to fetch metadata");
  }
  return res.json();
}

export async function fetchTopics(lang: Lang): Promise<{ demo_mode: boolean; topics: TopicSummary[] }> {
  const res = await fetch(`/api/topics?lang=${encodeURIComponent(lang)}`);
  if (!res.ok) {
    throw new Error("Failed to fetch topics");
  }
  return res.json();
}

export async function fetchAnswer(
  faqId: number,
  lang: Lang,
  recordTap: boolean = true
): Promise<AnswerPayload> {
  const res = await fetch(
    `/api/answers/${faqId}?lang=${encodeURIComponent(lang)}&record_tap=${recordTap}`
  );
  if (!res.ok) {
    throw new Error("Failed to fetch answer");
  }
  return res.json();
}

export async function fetchBundle(lang: Lang): Promise<BundleResponse> {
  const res = await fetch(`/api/bundle?lang=${encodeURIComponent(lang)}`);
  if (!res.ok) {
    throw new Error("Failed to fetch offline bundle");
  }
  return res.json();
}

export async function fetchClinics(state?: string): Promise<{ clinics: Clinic[] }> {
  const qs = state ? `?state=${encodeURIComponent(state)}` : "";
  const res = await fetch(`/api/clinics${qs}`);
  if (!res.ok) {
    throw new Error("Failed to fetch clinics");
  }
  return res.json();
}

export async function sendFeedback(payload: {
  log_id?: number | null;
  faq_id?: number;
  lang?: Lang;
  rating: 1 | -1;
}): Promise<void> {
  await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function askVoice(
  audioBlob: Blob,
  lang: Lang,
  durationSeconds: number
): Promise<AskResponse> {
  const form = new FormData();
  const mime = (audioBlob.type || "").toLowerCase();
  const ext = mime.includes("ogg")
    ? "ogg"
    : mime.includes("mp4") || mime.includes("m4a") || mime.includes("aac")
    ? "mp4"
    : mime.includes("wav")
    ? "wav"
    : "webm";
  form.append("audio", audioBlob, `question.${ext}`);
  form.append("lang", lang);
  form.append("duration_seconds", String(durationSeconds));
  const res = await fetch("/api/ask", {
    method: "POST",
    body: form
  });
  if (!res.ok) {
    let detail = "Voice upload failed";
    try {
      const errBody = (await res.json()) as { detail?: string };
      if (typeof errBody?.detail === "string" && errBody.detail.trim()) {
        detail = errBody.detail.trim();
      }
    } catch {
      // Ignore non-JSON error body
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function askText(text: string, lang: Lang): Promise<AskResponse> {
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, lang })
  });
  if (!res.ok) {
    throw new Error("Question request failed");
  }
  return res.json();
}

export async function fetchTtsAudio(text: string, lang: Lang): Promise<Blob> {
  const res = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, lang })
  });
  if (!res.ok) {
    throw new Error("TTS request failed");
  }
  return res.blob();
}
