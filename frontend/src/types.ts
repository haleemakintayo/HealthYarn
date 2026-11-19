export type Lang = "yo" | "pcm" | "en";
export type DiagnosisStatus = "undiagnosed" | "diagnosed" | "unspecified";

export interface QuestionSummary {
  faq_id: number;
  intent_key: string;
  question: string;
  question_audio_url: string | null;
}

export interface TopicSummary {
  id: number;
  slug: string;
  icon: string;
  sort_order: number;
  name: string;
  description: string;
  questions: QuestionSummary[];
}

export interface BundleItem {
  faq_id: number;
  intent_key: string;
  source_reference: string;
  question: string;
  answer_text: string;
  undiagnosed_text?: string;
  diagnosed_text?: string;
  question_audio_url: string | null;
  answer_audio_url: string | null;
  undiagnosed_audio_url?: string | null;
  diagnosed_audio_url?: string | null;
}

export interface BundleTopic {
  id: number;
  slug: string;
  icon: string;
  sort_order: number;
  name: string;
  description: string;
  items: BundleItem[];
}

export interface SystemMessageEntry {
  text: string;
  audio_url: string | null;
}

export interface Clinic {
  id: number;
  name: string;
  lga: string;
  state: string;
  phone: string;
  type: string;
  lat: number | null;
  lng: number | null;
}

export interface BundleResponse {
  lang: Lang;
  version_hash: string;
  demo_mode: boolean;
  content_reviewed?: boolean;
  meta: {
    content_last_updated: string;
    clinical_reviewers: string;
    language_reviewers: string;
  };
  topics: BundleTopic[];
  system_messages: Record<string, SystemMessageEntry>;
  clinics: Clinic[];
  audio_urls: string[];
}

export type AnswerSource = "verified_faq" | "ai_guardrailed";

export interface AnswerPayload {
  faq_id: number;
  answer_source?: AnswerSource;
  suggest_clinics?: boolean;
  intent_key: string;
  topic_slug?: string;
  topic_name?: string;
  lang: Lang;
  question: string;
  answer_text: string;
  undiagnosed_text?: string;
  diagnosed_text?: string;
  question_audio_url: string | null;
  answer_audio_url: string | null;
  undiagnosed_audio_url?: string | null;
  diagnosed_audio_url?: string | null;
  diagnosis_status?: DiagnosisStatus;
  source_reference?: string;
  disclaimer_text?: string;
  disclaimer_audio_url?: string | null;
  demo_mode?: boolean;
  log_id?: number | null;
  confidence?: number;
}

export interface UnsureCandidate {
  faq_id: number;
  question: string;
  question_audio_url: string | null;
}

export type AskResponse =
  | {
      type: "answer";
      faq_id: number;
      answer_source?: AnswerSource;
      suggest_clinics?: boolean;
      intent_key?: string;
      topic_slug?: string;
      topic_name?: string;
      question: string;
      answer_text: string;
      undiagnosed_text?: string;
      diagnosed_text?: string;
      answer_audio_url: string | null;
      undiagnosed_audio_url?: string | null;
      diagnosed_audio_url?: string | null;
      diagnosis_status?: DiagnosisStatus;
      disclaimer_text?: string;
      disclaimer_audio_url?: string | null;
      source_reference?: string;
      confidence: number;
      log_id: number | null;
    }
  | {
      type: "unsure";
      heard_text?: string | null;
      message_text?: string;
      message_audio_url?: string | null;
      candidates: UnsureCandidate[];
      log_id: number | null;
    }
  | {
      type: "red_flag";
      message_text: string;
      message_audio_url: string | null;
      clinics: Clinic[];
      log_id: number | null;
    }
  | {
      type: "error";
      code: string;
      message_text?: string;
      message_audio_url?: string | null;
      log_id?: number | null;
    };
