import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { AboutView } from "../components/AboutView";
import { RedFlagAlertView } from "../components/RedFlagAlertView";
import { AnswerView } from "../components/AnswerView";
import { encodeMonoWav } from "../hooks/useVoiceRecorder";

const MOCK_BUNDLE = {
  lang: "en",
  version_hash: "abc123",
  demo_mode: false,
  content_reviewed: true,
  meta: {
    content_last_updated: "2026-11-16",
    clinical_reviewers: "Dr. Test",
    language_reviewers: "Team Test"
  },
  topics: [
    {
      id: 1,
      slug: "child_diarrhoea_ors",
      icon: "droplet",
      sort_order: 1,
      name: "Child Diarrhoea & ORS",
      description: "Mixing ORS safely",
      items: [
        {
          faq_id: 9,
          intent_key: "ors_how_to_prepare",
          source_reference: "WHO ORS Guide",
          question: "How do I prepare ORS for my child?",
          answer_text: "Mix one sachet in 1L clean water.",
          question_audio_url: "/static/audio/en/ors_q.ogg",
          answer_audio_url: "/static/audio/en/ors_a.ogg"
        }
      ]
    }
  ],
  system_messages: {
    disclaimer: {
      text: "General health information only.",
      audio_url: "/static/audio/en/disclaimer.ogg"
    }
  },
  clinics: [
    {
      id: 1,
      name: "Ikeja Primary Health Centre",
      lga: "Ikeja",
      state: "Lagos",
      phone: "+2348001122001",
      type: "Primary Health Centre",
      lat: 6.6,
      lng: 3.35
    }
  ],
  audio_urls: ["/static/audio/en/ors_q.ogg", "/static/audio/en/ors_a.ogg"]
};

describe("HealthYarn Landing & App Core Flows", () => {
  const playedUrls: string[] = [];
  let mockContentReviewed = true;

  beforeEach(() => {
    localStorage.clear();
    playedUrls.length = 0;
    mockContentReviewed = true;
    window.history.pushState({}, "", "/");
    document.documentElement.lang = "en";

    class MockAudio {
      src: string;
      playbackRate = 1.0;
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(src: string) {
        this.src = src;
      }
      play() {
        playedUrls.push(this.src);
        return Promise.resolve();
      }
      pause() {}
    }

    vi.stubGlobal("scrollTo", vi.fn());
    vi.stubGlobal("Audio", MockAudio);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/api/topics")) {
          return new Response(
            JSON.stringify({
              lang: "en",
              demo_mode: !mockContentReviewed,
              topics: MOCK_BUNDLE.topics.map((t) => ({
                id: t.id,
                slug: t.slug,
                icon: t.icon,
                sort_order: t.sort_order,
                name: t.name,
                description: t.description,
                questions: t.items
              }))
            }),
            { status: 200 }
          );
        }
        if (url.includes("/api/bundle")) {
          return new Response(
            JSON.stringify({ ...MOCK_BUNDLE, content_reviewed: mockContentReviewed }),
            { status: 200 }
          );
        }
        if (url.includes("/api/clinics")) {
          return new Response(JSON.stringify({ clinics: MOCK_BUNDLE.clinics }), { status: 200 });
        }
        if (url.includes("/api/meta")) {
          return new Response(
            JSON.stringify({
              demo_mode: !mockContentReviewed,
              content_reviewed: mockContentReviewed,
              content_last_updated: "2026-11-16",
              clinical_reviewers: "Dr. Test",
              language_reviewers: "Team Test",
              sample_audio: {
                en: "/static/audio/en/ors_a.ogg",
                yo: "/static/audio/yo/ors_a.ogg",
                pcm: null
              },
              hero_audio: { en: null, yo: null, pcm: null }
            }),
            { status: 200 }
          );
        }
        if (url.includes("/api/answers/9")) {
          const isYo = url.includes("lang=yo");
          return new Response(
            JSON.stringify({
              faq_id: 9,
              intent_key: "ors_how_to_prepare",
              lang: isYo ? "yo" : "en",
              question: isYo
                ? "Báwo ni mo ṣe lè pò omi iyọ̀ ORS?"
                : MOCK_BUNDLE.topics[0].items[0].question,
              answer_text: isYo
                ? "Pò àpò ORS kan sínú omi mímọ́ lítà kan."
                : MOCK_BUNDLE.topics[0].items[0].answer_text,
              question_audio_url: isYo ? "/static/audio/yo/ors_q.ogg" : "/static/audio/en/ors_q.ogg",
              answer_audio_url: isYo ? "/static/audio/yo/ors_a.ogg" : "/static/audio/en/ors_a.ogg",
              disclaimer_text: isYo
                ? "Ìmọ̀ràn ìlera gbogbogbò nìkan."
                : "General health information only.",
              disclaimer_audio_url: "/static/audio/en/disclaimer.ogg",
              log_id: 42
            }),
            { status: 200 }
          );
        }
        return new Response("{}", { status: 200 });
      })
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("switches landing page copy across EN, Pidgin, and Yorùbá with zero Igbo and plays sample clip", async () => {
    const { container } = render(<App />);

    expect(
      await screen.findByText("Ask in your language. Hear an answer you can trust.")
    ).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en");
    expect(container.textContent).not.toMatch(/\bIgbo\b/i);

    const sampleBtn = await screen.findByRole("button", { name: "Hear a sample answer" });
    fireEvent.click(sampleBtn);
    expect(playedUrls).toContain("/static/audio/en/ors_a.ogg");

    fireEvent.click(screen.getAllByRole("button", { name: "Pidgin" })[0]);
    expect(
      await screen.findByText("Ask for your own language. Hear answer wey you fit trust.")
    ).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("pcm");
    expect(screen.queryByRole("button", { name: "Hear sample answer" })).toBeNull();

    fireEvent.click(screen.getAllByRole("button", { name: "Yorùbá" })[0]);
    expect(
      await screen.findByText("Béèrè ní èdè rẹ. Gbọ́ ìdáhùn tí o lè gbẹ́kẹ̀lé.")
    ).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("yo");
    expect(container.textContent).not.toMatch(/\bIgbo\b/i);
  });

  it("shows 'Demo content, under review' when CONTENT_REVIEWED is false", async () => {
    mockContentReviewed = false;
    render(<App />);
    expect(await screen.findByText("Demo content, under review")).toBeInTheDocument();
  });

  it("navigates from landing page CTA to /app preserving selected language", async () => {
    render(<App />);
    fireEvent.click(screen.getAllByRole("button", { name: "Yorùbá" })[0]);
    const ctas = await screen.findAllByRole("button", { name: "Béèrè ìbéèrè" });
    fireEvent.click(ctas[0]);

    expect(window.location.pathname).toBe("/app");
    expect(localStorage.getItem("healthyarn_lang")).toBe("yo");
    expect(await screen.findByText("Àwọn àkòrí ìlera")).toBeInTheDocument();
  });

  it("remembers language selection in /app language picker", async () => {
    window.history.pushState({}, "", "/app");
    render(<App />);
    const yorubaBtn = await screen.findByRole("button", { name: /Yorùbá —/i });
    fireEvent.click(yorubaBtn);
    expect(localStorage.getItem("healthyarn_lang")).toBe("yo");
    expect(await screen.findByText("Àwọn àkòrí ìlera")).toBeInTheDocument();
  });

  it("renders answer screen and plays audio", async () => {
    const playSeq = vi.fn();
    render(
      <AnswerView
        lang="en"
        answer={{
          faq_id: 9,
          intent_key: "ors_how_to_prepare",
          lang: "en",
          question: "How do I prepare ORS?",
          answer_text: "Mix one sachet in 1L clean water.",
          question_audio_url: "/static/audio/en/ors_q.ogg",
          answer_audio_url: "/static/audio/en/ors_a.ogg",
          disclaimer_text: "General info only.",
          disclaimer_audio_url: "/static/audio/en/disclaimer.ogg",
          log_id: 1
        }}
        autoplayEnabled={true}
        isPlaying={false}
        playbackRate={1.0}
        onPlayAnswerSequence={playSeq}
        onToggleSpeed={vi.fn()}
        onFeedback={vi.fn(async () => {})}
        onResetHome={vi.fn()}
      />
    );

    expect(screen.getByText("Mix one sachet in 1L clean water.")).toBeInTheDocument();
    expect(playSeq).toHaveBeenCalledWith(
      "/static/audio/en/ors_a.ogg",
      "/static/audio/en/disclaimer.ogg",
      "Mix one sachet in 1L clean water."
    );
  });

  it("prevents dismissing RedFlagAlertView for 5 seconds", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    const onPlayClip = vi.fn();
    render(
      <RedFlagAlertView
        lang="en"
        messageText="Urgent medical danger sign."
        messageAudioUrl="/static/audio/en/red_flag.ogg"
        clinics={MOCK_BUNDLE.clinics}
        autoplayEnabled={true}
        onPlayClip={onPlayClip}
        onDismiss={onDismiss}
      />
    );

    const returnBtn = screen.getByRole("button", { name: /I understand/i });
    expect(returnBtn).toBeDisabled();
    expect(onPlayClip).toHaveBeenCalledWith("/static/audio/en/red_flag.ogg");

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(returnBtn).toBeDisabled();

    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(returnBtn).not.toBeDisabled();
    fireEvent.click(returnBtn);
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("shows cached topics and opens answers when offline", async () => {
    window.history.pushState({}, "", "/app");
    localStorage.setItem("healthyarn_lang", "en");
    localStorage.setItem("healthyarn_bundle_v1_en", JSON.stringify(MOCK_BUNDLE));
    vi.stubGlobal("navigator", { onLine: false });
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new Error("Network offline")))
    );

    render(<App />);
    expect(await screen.findByText(/Voice needs internet/i)).toBeInTheDocument();
    const topicBtn = await screen.findByRole("button", { name: /Child Diarrhoea & ORS/i });
    fireEvent.click(topicBtn);

    const qBtn = await screen.findByRole("button", {
      name: /Open answer: How do I prepare ORS/i
    });
    fireEvent.click(qBtn);

    await waitFor(() => {
      expect(screen.getByText("Mix one sachet in 1L clean water.")).toBeInTheDocument();
    });
  });

  it("clears stale English topics if switching to Pidgin fails or has no cache", async () => {
    window.history.pushState({}, "", "/app");
    localStorage.setItem("healthyarn_lang", "en");

    render(<App />);
    expect(await screen.findByRole("button", { name: /Child Diarrhoea & ORS/i })).toBeInTheDocument();

    // Simulate backend rejecting lang=pcm (e.g., stale server)
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response('{"detail":"Unsupported language"}', { status: 400 }))
    );

    fireEvent.click(screen.getAllByRole("button", { name: "Pidgin" })[0]);
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: /Child Diarrhoea & ORS/i })).toBeNull();
    });
  });

  it("navigates across Overview (/), Voice App (/app), About (/about), and Staff Sign In (/admin) via unified navbar", async () => {
    render(<App />);
    expect(
      await screen.findByText("Ask in your language. Hear an answer you can trust.")
    ).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "About" })[0]);
    expect(window.location.pathname).toBe("/about");
    expect(await screen.findByText("Why we made HealthYarn")).toBeInTheDocument();
    expect(
      screen.getByText("Every answer passes through people before it reaches you.")
    ).toBeInTheDocument();
    expect(screen.getByText(/YarnGPT by Saheed Azeez/i)).toBeInTheDocument();
    expect(screen.getByText(/Spitch Speech AI/i)).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Staff" })[0]);
    expect(window.location.pathname).toBe("/admin");
    expect(await screen.findByText("Staff Sign In", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(
      screen.getByText("Clinical & Language Governance Portal")
    ).toBeInTheDocument();
    // Password toggle works cleanly and no hardcoded demo password is shown on screen
    const pwInput = screen.getByLabelText("Password") as HTMLInputElement;
    expect(pwInput.type).toBe("password");
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(pwInput.type).toBe("text");
    expect(document.body.textContent).not.toMatch(/HealthYarnAdmin2026/);

    fireEvent.click(screen.getAllByRole("button", { name: "Voice App" })[0]);
    expect(window.location.pathname).toBe("/app");
  });

  it("translates an open answer in-place when switching language in the /app navbar", async () => {
    window.history.pushState({}, "", "/app");
    localStorage.setItem("healthyarn_lang", "en");

    render(<App />);
    const topicBtn = await screen.findByRole("button", { name: /Child Diarrhoea & ORS/i });
    fireEvent.click(topicBtn);

    const qBtn = await screen.findByRole("button", {
      name: /Open answer: How do I prepare ORS/i
    });
    fireEvent.click(qBtn);
    expect(await screen.findByText("Mix one sachet in 1L clean water.")).toBeInTheDocument();

    // Switch to Yorùbá inside the open Answer screen -> translates in-place without kicking back to Home
    fireEvent.click(screen.getAllByRole("button", { name: "Yorùbá" })[0]);
    await waitFor(() => {
      expect(screen.getByText("Pò àpò ORS kan sínú omi mímọ́ lítà kan.")).toBeInTheDocument();
    });
  });

  it("completes Hold-to-Talk flow on pointerDown -> pointerUp and handles quick-release before getUserMedia", async () => {
    window.history.pushState({}, "", "/app");
    localStorage.setItem("healthyarn_lang", "en");

    let askUploads = 0;
    const stopTrack = vi.fn();
    let resolveMic: ((stream: MediaStream) => void) | null = null;

    class MockMediaRecorder {
      static isTypeSupported(mime: string) {
        return mime.startsWith("audio/webm");
      }
      mimeType = "audio/webm;codecs=opus";
      state: RecordingState = "inactive";
      ondataavailable: ((ev: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      start() {
        this.state = "recording";
      }
      requestData() {
        this.ondataavailable?.({ data: new Blob([new Uint8Array(512)], { type: this.mimeType }) });
      }
      stop() {
        this.state = "inactive";
        this.ondataavailable?.({ data: new Blob([new Uint8Array(512)], { type: this.mimeType }) });
        this.onstop?.();
      }
    }

    vi.stubGlobal("MediaRecorder", MockMediaRecorder);
    vi.stubGlobal("navigator", {
      onLine: true,
      mediaDevices: {
        getUserMedia: vi.fn(
          () =>
            new Promise<MediaStream>((resolve) => {
              resolveMic = resolve;
            })
        )
      }
    });

    const baseFetch = globalThis.fetch as ReturnType<typeof vi.fn>;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === "/api/ask" && init?.method === "POST") {
          askUploads += 1;
          return new Response(
            JSON.stringify({
              type: "answer",
              faq_id: 9,
              question: "How do I prepare ORS for my child?",
              answer_text: "Mix one sachet in 1L clean water.",
              answer_audio_url: "/static/audio/en/ors_a.ogg",
              disclaimer_text: "General health information only.",
              disclaimer_audio_url: "/static/audio/en/disclaimer.ogg",
              source_reference: "WHO ORS Guide",
              confidence: 0.91,
              log_id: 55
            }),
            { status: 200 }
          );
        }
        return baseFetch(input, init);
      })
    );

    render(<App />);
    // Default accessible mode is Tap-to-Speak; switch to Hold-to-Speak to test hold gesture
    expect(await screen.findByRole("button", { name: "Tap to start speaking" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Switch to hold-to-speak mode" }));
    const holdBtn = await screen.findByRole("button", { name: "Hold to speak" });

    // 1. Quick release while getUserMedia is still pending -> stops mic stream cleanly & asks user to hold
    fireEvent.pointerDown(holdBtn, { pointerId: 1, button: 0 });
    expect(
      await screen.findByRole("heading", { name: "Opening microphone…" })
    ).toBeInTheDocument();
    fireEvent.pointerUp(holdBtn, { pointerId: 1 });
    await act(async () => {
      resolveMic?.({ getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream);
    });
    expect(stopTrack).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Hold the button while speaking, then release."
    );
    expect(askUploads).toBe(0);

    // 2. Proper Hold -> Speak (>300ms) -> Release on the kept button -> uploads audio & opens answer
    const micReady = () =>
      ({ getTracks: () => [{ stop: stopTrack }] }) as unknown as MediaStream;
    (navigator.mediaDevices.getUserMedia as ReturnType<typeof vi.fn>).mockImplementationOnce(() =>
      Promise.resolve(micReady())
    );

    const origNow = Date.now;
    let fakeNow = 1_000_000;
    vi.spyOn(Date, "now").mockImplementation(() => fakeNow);

    try {
      await act(async () => {
        fireEvent.pointerDown(screen.getByRole("button", { name: "Hold to speak" }), {
          pointerId: 2,
          button: 0
        });
      });

      expect(await screen.findByText("Release button to send")).toBeInTheDocument();
      fakeNow += 1200;

      await act(async () => {
        fireEvent.pointerUp(window);
      });

      expect(askUploads).toBe(1);
      expect(await screen.findByText("Mix one sachet in 1L clean water.")).toBeInTheDocument();
    } finally {
      Date.now = origNow;
    }
  });

  it("renders /about across all 3 languages, hides empty config blocks, gates CONTENT_REVIEWED, and routes to /credits & /privacy", async () => {
    window.history.pushState({}, "", "/about");
    render(<App />);

    // Default empty config hides Section 5 ("Who made HealthYarn") & empty review date
    expect(await screen.findByText("Why we made HealthYarn")).toBeInTheDocument();
    expect(screen.queryByText("Who made HealthYarn")).toBeNull();
    expect(screen.queryByText(/Content last reviewed:/i)).toBeNull();
    expect(screen.getByText("Checked by a doctor, nurse or pharmacist")).toBeInTheDocument();

    // Section 1 read-aloud button plays pre-synthesised Spitch audio clip
    fireEvent.click(
      screen.getByRole("button", { name: /Listen to this section aloud: Why we made HealthYarn/i })
    );
    expect(playedUrls).toContain("/static/audio/about/en/section_1.ogg");

    // Exact Pidgin & Yorùbá opening strings
    fireEvent.click(screen.getAllByRole("button", { name: "Pidgin" })[0]);
    expect(await screen.findByText("Why we make HealthYarn")).toBeInTheDocument();
    expect(
      screen.getByText("Better health information no suppose depend on how well you sabi read English.")
    ).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Yorùbá" })[0]);
    expect(await screen.findByText("Ìdí tí a fi ṣe HealthYarn")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Ìmọ̀ nípa ìlerà tó dára kò gbọ́dọ̀ sínúù bí o ṣe mọ̀ èdè Gẹ̀ẹ́sì kà tó."
      )
    ).toBeInTheDocument();

    // Navigate to /credits & /privacy inside app
    fireEvent.click(screen.getAllByRole("button", { name: "English" })[0]);
    fireEvent.click(await screen.findByRole("button", { name: /Full credits and licences/i }));
    expect(window.location.pathname).toBe("/credits");
    expect(await screen.findByText("Full Credits & Licences")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Privacy" })[0]);
    expect(window.location.pathname).toBe("/privacy");
    expect(await screen.findByText("Privacy Notice (NDPA 2023)")).toBeInTheDocument();
  });

  it("renders populated AboutConfig team/reviewers/institution/date and gates clinical phrasing when contentReviewed=false", () => {
    const { rerender } = render(
      <AboutView
        lang="en"
        contentReviewed={true}
        config={{
          team: [
            { name: "Adaeze Okonkwo", role: "Backend Engineer", contribution: "API & matching" },
            {
              name: "Tunde Bakare",
              role: "UI Designer",
              contribution: "Voice interface",
              photo: "/static/tunde.jpg"
            }
          ],
          reviewers: [
            {
              name: "Dr. Bisi Adeyemi",
              profession: "Pharmacist",
              reviewed: "Medicine safety answers",
              date: "2026-11-16"
            }
          ],
          institution: "University of Lagos",
          sttProvider: "Spitch Speech AI",
          contactEmail: "team@example.org",
          contentLastReviewed: "2026-11-16",
          licensesRepoUrl: ""
        }}
        onSelectLang={vi.fn()}
        onNavigateRoute={vi.fn()}
      />
    );

    expect(screen.getByText("Who made HealthYarn")).toBeInTheDocument();
    expect(screen.getByText("AO")).toBeInTheDocument();
    expect(screen.getByAltText("Tunde Bakare")).toBeInTheDocument();
    expect(screen.getByText("Pharmacist")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Built by students at University of Lagos for the Nigeria Computer Society IT Development Contest 2026."
      )
    ).toBeInTheDocument();
    expect(screen.getByText("Content last reviewed: 2026-11-16")).toBeInTheDocument();
    expect(screen.getByText("Checked by a doctor, nurse or pharmacist")).toBeInTheDocument();

    rerender(
      <AboutView
        lang="en"
        contentReviewed={false}
        config={{
          team: [{ name: "Adaeze Okonkwo", role: "Engineer", contribution: "API" }],
          reviewers: [
            { name: "Dr. Bisi Adeyemi", profession: "Pharmacist", reviewed: "Drafts", date: "2026-11-16" }
          ],
          institution: "",
          sttProvider: "Spitch Speech AI",
          contactEmail: "team@example.org",
          contentLastReviewed: "2026-11-16",
          licensesRepoUrl: ""
        }}
        onSelectLang={vi.fn()}
        onNavigateRoute={vi.fn()}
      />
    );

    expect(screen.queryByText("Checked by a doctor, nurse or pharmacist")).toBeNull();
    expect(screen.queryByText(/Content last reviewed:/i)).toBeNull();
    expect(screen.queryByText("Pharmacist")).toBeNull();
  });

  it("pads short mono audio via encodeMonoWav to >= 2.2s WAV for YarnGPT ASR", async () => {
    const halfSecond = new Float32Array(8000);
    const wavBlob = encodeMonoWav(halfSecond, 16000, 2.2, 16000);
    expect(wavBlob.type).toBe("audio/wav");
    // 44-byte RIFF header + 2.2s * 16000Hz * 2 bytes = 70444 bytes
    expect(wavBlob.size).toBe(70444);
  });

  it("renders the 2-pill diagnosis toggle on AnswerView, auto-selects diagnosed track, and switches audio", () => {
    const onPlay = vi.fn();
    render(
      <AnswerView
        lang="en"
        answer={{
          faq_id: 1,
          intent_key: "malaria_test_before_treat",
          lang: "en",
          question: "Should I take malaria drugs before getting tested?",
          answer_text: "Default summary answer.",
          undiagnosed_text: "Get an RDT test before starting malaria medicine.",
          diagnosed_text: "Finish every prescribed ACT tablet over all 3 days.",
          question_audio_url: "/static/audio/en/q.ogg",
          answer_audio_url: "/static/audio/en/default.ogg",
          undiagnosed_audio_url: "/static/audio/en/undiag.ogg",
          diagnosed_audio_url: "/static/audio/en/diag.ogg",
          diagnosis_status: "diagnosed",
          disclaimer_text: "General info only.",
          disclaimer_audio_url: "/static/audio/en/disclaimer.ogg"
        }}
        autoplayEnabled={true}
        isPlaying={false}
        playbackRate={1.0}
        onPlayAnswerSequence={onPlay}
        onToggleSpeed={vi.fn()}
        onFeedback={vi.fn(async () => {})}
        onResetHome={vi.fn()}
      />
    );

    expect(screen.getByText("Verified HealthYarn Guide")).toBeInTheDocument();
    expect(screen.getByText("Selected from your question — tap to switch")).toBeInTheDocument();
    expect(screen.getByText("Finish every prescribed ACT tablet over all 3 days.")).toBeInTheDocument();
    expect(onPlay).toHaveBeenLastCalledWith(
      "/static/audio/en/diag.ogg",
      "/static/audio/en/disclaimer.ogg",
      "Finish every prescribed ACT tablet over all 3 days."
    );

    const undiagBtn = screen.getByRole("button", { name: "Not yet tested / diagnosed" });
    const diagBtn = screen.getByRole("button", { name: "Diagnosed by a doctor" });
    expect(diagBtn).toHaveAttribute("aria-pressed", "true");
    expect(undiagBtn).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(undiagBtn);
    expect(undiagBtn).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Get an RDT test before starting malaria medicine.")).toBeInTheDocument();
    expect(onPlay).toHaveBeenLastCalledWith(
      "/static/audio/en/undiag.ogg",
      "/static/audio/en/disclaimer.ogg",
      "Get an RDT test before starting malaria medicine."
    );
  });

  it("renders progressive 3-step bar, collapsible typed input, starter chips, Stop audio bar, and Abeokuta clinics drawer", async () => {
    localStorage.setItem("healthyarn_lang", "en");
    window.history.pushState({}, "", "/app");
    render(<App />);

    // Step 1 active + starter chips + collapsed typed question box
    const stepNav = await screen.findByRole("navigation", { name: "Health guide steps" });
    expect(stepNav.querySelector('[aria-current="step"]')).toHaveTextContent("Ask");
    expect(screen.getByText("Try asking")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Type a question (test / fallback)")).toBeNull();

    // Expand progressive typing toggle
    fireEvent.click(screen.getByRole("button", { name: "Type a question instead" }));
    expect(screen.getByPlaceholderText("Type a question (test / fallback)")).toBeInTheDocument();

    // Tap speaker preview plays clip; tap starter chip text -> transitions straight to Step 3 AnswerView
    fireEvent.click(
      screen.getByRole("button", { name: "Hear question: How do I prepare ORS for my child?" })
    );
    fireEvent.click(
      screen.getByRole("button", { name: "How do I prepare ORS for my child?" })
    );
    expect(await screen.findByText("Mix one sachet in 1L clean water.")).toBeInTheDocument();
    expect(stepNav.querySelector('[aria-current="step"]')).toHaveTextContent("Answer");

    // Playing state shows Stop audio control + Speaking indicator, and Nearby Hospitals drawer toggles cleanly
    expect(screen.getByRole("button", { name: "Stop audio" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Stop audio" }));
    expect(screen.getByRole("button", { name: "Listen to answer" })).toBeInTheDocument();

    const clinicsToggle = screen.getByRole("button", {
      name: "Nearby hospitals & clinics (Abeokuta)"
    });
    fireEvent.click(clinicsToggle);
    expect(await screen.findByText("Ikeja Primary Health Centre")).toBeInTheDocument();
  });

  it("renders Tier 3 AI guardrailed badge, auto-expands Abeokuta clinics when suggest_clinics is true, and plays ephemeral /api/tts audio", async () => {
    localStorage.setItem("healthyarn_lang", "en");
    window.history.pushState({}, "", "/app");

    const baseFetch = globalThis.fetch as unknown as (
      input: RequestInfo | URL,
      init?: RequestInit
    ) => Promise<Response>;
    const ttsCalls: string[] = [];

    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:ephemeral-tts-1"),
      revokeObjectURL: vi.fn()
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/api/ask")) {
          return new Response(
            JSON.stringify({
              type: "answer",
              faq_id: 0,
              answer_source: "ai_guardrailed",
              suggest_clinics: true,
              intent_key: "ai_guardrailed",
              lang: "en",
              question: "i think my wife is in labor, what should i do",
              answer_text: "Prepare to go to the nearest maternity clinic or hospital immediately.",
              undiagnosed_text: "Prepare to go to the nearest maternity clinic or hospital immediately.",
              diagnosed_text: "Follow her antenatal birth plan and go to the hospital now.",
              answer_audio_url: null,
              undiagnosed_audio_url: null,
              diagnosed_audio_url: null,
              diagnosis_status: "unspecified",
              disclaimer_text: "General health information only.",
              disclaimer_audio_url: "/static/audio/en/disclaimer.ogg",
              log_id: 99
            }),
            { status: 200 }
          );
        }
        if (url.includes("/api/tts")) {
          ttsCalls.push(String(init?.body ?? ""));
          return new Response(new Blob(["OggS"], { type: "audio/ogg" }), { status: 200 });
        }
        return baseFetch(input, init);
      })
    );

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Type a question instead" }));
    fireEvent.change(screen.getByPlaceholderText("Type a question (test / fallback)"), {
      target: { value: "i think my wife is in labor, what should i do" }
    });
    fireEvent.submit(screen.getByPlaceholderText("Type a question (test / fallback)").closest("form")!);

    expect(await screen.findByText("AI General Health Info — consult a clinic")).toBeInTheDocument();
    expect(
      screen.getByText("Prepare to go to the nearest maternity clinic or hospital immediately.")
    ).toBeInTheDocument();
    // suggest_clinics: true auto-expands the nearby clinic list without clicking
    expect(screen.getByText("Ikeja Primary Health Centre")).toBeInTheDocument();

    await waitFor(() => {
      expect(ttsCalls.length).toBeGreaterThan(0);
      expect(playedUrls).toContain("blob:ephemeral-tts-1");
    });
  });

  it("falls back to window.speechSynthesis when /api/tts fails", async () => {
    localStorage.setItem("healthyarn_lang", "en");
    window.history.pushState({}, "", "/app");

    const baseFetch = globalThis.fetch as unknown as (
      input: RequestInfo | URL,
      init?: RequestInit
    ) => Promise<Response>;
    const spokenTexts: string[] = [];

    class MockUtterance {
      text: string;
      lang = "";
      rate = 1;
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(text: string) {
        this.text = text;
      }
    }

    vi.stubGlobal("SpeechSynthesisUtterance", MockUtterance);
    vi.stubGlobal("speechSynthesis", {
      speak: vi.fn((utt: MockUtterance) => {
        spokenTexts.push(utt.text);
        utt.onend?.();
      }),
      cancel: vi.fn()
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/api/ask")) {
          return new Response(
            JSON.stringify({
              type: "answer",
              faq_id: 0,
              answer_source: "ai_guardrailed",
              suggest_clinics: false,
              intent_key: "ai_guardrailed",
              lang: "en",
              question: "How can I prevent dehydration during heatwave?",
              answer_text: "Drink clean water regularly throughout the day.",
              undiagnosed_text: "Drink clean water regularly throughout the day.",
              diagnosed_text: "Follow your clinician fluid advice and drink clean water regularly.",
              answer_audio_url: null,
              undiagnosed_audio_url: null,
              diagnosed_audio_url: null,
              diagnosis_status: "unspecified",
              disclaimer_text: "General health information only.",
              disclaimer_audio_url: null,
              log_id: 100
            }),
            { status: 200 }
          );
        }
        if (url.includes("/api/tts")) {
          return new Response("Unavailable", { status: 503 });
        }
        return baseFetch(input, init);
      })
    );

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Type a question instead" }));
    fireEvent.change(screen.getByPlaceholderText("Type a question (test / fallback)"), {
      target: { value: "How can I prevent dehydration during heatwave?" }
    });
    fireEvent.submit(screen.getByPlaceholderText("Type a question (test / fallback)").closest("form")!);

    expect(await screen.findByText("AI General Health Info — consult a clinic")).toBeInTheDocument();
    await waitFor(() => {
      expect(spokenTexts).toContain("Drink clean water regularly throughout the day.");
    });
  });

  it("blocks robotic English SpeechSynthesis fallback on Yorùbá when /api/tts fails without a native yo voice", async () => {
    localStorage.setItem("healthyarn_lang", "yo");
    window.history.pushState({}, "", "/app");

    const baseFetch = globalThis.fetch as unknown as (
      input: RequestInfo | URL,
      init?: RequestInit
    ) => Promise<Response>;
    const speakSpy = vi.fn();

    class MockUtterance {
      text: string;
      lang = "";
      rate = 1;
      onend: (() => void) | null = null;
      onerror: (() => void) | null = null;
      constructor(text: string) {
        this.text = text;
      }
    }

    vi.stubGlobal("SpeechSynthesisUtterance", MockUtterance);
    vi.stubGlobal("speechSynthesis", {
      getVoices: vi.fn(() => [{ lang: "en-GB", name: "English UK" }]),
      speak: speakSpy,
      cancel: vi.fn()
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/api/ask")) {
          return new Response(
            JSON.stringify({
              type: "answer",
              faq_id: 0,
              answer_source: "ai_guardrailed",
              suggest_clinics: true,
              intent_key: "ai_guardrailed",
              lang: "yo",
              question: "Mo rò pé ìyàwó mi ti wà nínú ìrọbí",
              answer_text: "Ẹ mú ìyàwó yín lọ sí ilé ìwòsàn lẹ́sẹ̀kẹsẹ̀.",
              undiagnosed_text: "Ẹ mú ìyàwó yín lọ sí ilé ìwòsàn lẹ́sẹ̀kẹsẹ̀.",
              diagnosed_text: "Ẹ tẹ̀ lé ìtọ́ni agbebí lọ sí ilé ìbí.",
              answer_audio_url: null,
              undiagnosed_audio_url: null,
              diagnosed_audio_url: null,
              diagnosis_status: "unspecified",
              disclaimer_text: "Ìmọ̀ràn ìlera gbogbogbò nìkan.",
              disclaimer_audio_url: "/static/audio/yo/disclaimer.ogg",
              log_id: 101
            }),
            { status: 200 }
          );
        }
        if (url.includes("/api/tts")) {
          return new Response("Unavailable", { status: 503 });
        }
        return baseFetch(input, init);
      })
    );

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Kọ ìbéèrè rẹ dípò sísọ̀rọ̀" }));
    fireEvent.change(screen.getByPlaceholderText("Kọ ìbéèrè rẹ (fún àyẹ̀wò)"), {
      target: { value: "Mo rò pé ìyàwó mi ti wà nínú ìrọbí" }
    });
    fireEvent.submit(screen.getByPlaceholderText("Kọ ìbéèrè rẹ (fún àyẹ̀wò)").closest("form")!);

    expect(
      await screen.findByText(
        "Ohùn Yorùbá alààyè kò sí lọ́wọ́lọ́wọ́. O lè ka ìtọ́sọ́nà ìsàlẹ̀ tàbí gbọ́ àkòrí tí a ti fọwọ́ sí."
      )
    ).toBeInTheDocument();
    expect(speakSpy).not.toHaveBeenCalled();
  });

  it("translates an open Tier 3 answer in-place to Yorùbá via /api/ask instead of /api/answers/0", async () => {
    localStorage.setItem("healthyarn_lang", "en");
    window.history.pushState({}, "", "/app");

    const baseFetch = globalThis.fetch as unknown as (
      input: RequestInfo | URL,
      init?: RequestInit
    ) => Promise<Response>;
    const answer0Calls: string[] = [];

    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:yo-tts"),
      revokeObjectURL: vi.fn()
    });

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/api/answers/0")) {
          answer0Calls.push(url);
          return new Response("Not Found", { status: 404 });
        }
        if (url.includes("/api/ask")) {
          const parsed = JSON.parse(String(init?.body || "{}"));
          const reqLang = parsed.lang || "en";
          if (reqLang === "yo") {
            return new Response(
              JSON.stringify({
                type: "answer",
                faq_id: 0,
                answer_source: "ai_guardrailed",
                suggest_clinics: true,
                intent_key: "ai_guardrailed",
                lang: "yo",
                question: "my wife is in labor, what should I do",
                answer_text: "Ẹ mú ìyàwó yín lọ sí ilé ìwòsàn lẹ́sẹ̀kẹsẹ̀.",
                undiagnosed_text: "Ẹ mú ìyàwó yín lọ sí ilé ìwòsàn lẹ́sẹ̀kẹsẹ̀.",
                diagnosed_text: "Ẹ tẹ̀ lé ìtọ́ni agbebí lọ sí ilé ìbí.",
                answer_audio_url: null,
                undiagnosed_audio_url: null,
                diagnosed_audio_url: null,
                diagnosis_status: "unspecified",
                log_id: 103
              }),
              { status: 200 }
            );
          }
          return new Response(
            JSON.stringify({
              type: "answer",
              faq_id: 0,
              answer_source: "ai_guardrailed",
              suggest_clinics: true,
              intent_key: "ai_guardrailed",
              lang: "en",
              question: "my wife is in labor, what should I do",
              answer_text: "Head promptly to the maternity clinic.",
              undiagnosed_text: "Head promptly to the maternity clinic.",
              diagnosed_text: "Follow her midwife birth plan and go to the hospital.",
              answer_audio_url: null,
              undiagnosed_audio_url: null,
              diagnosed_audio_url: null,
              diagnosis_status: "unspecified",
              log_id: 102
            }),
            { status: 200 }
          );
        }
        if (url.includes("/api/tts")) {
          return new Response(new Blob(["OggS"], { type: "audio/ogg" }), { status: 200 });
        }
        return baseFetch(input, init);
      })
    );

    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Type a question instead" }));
    fireEvent.change(screen.getByPlaceholderText("Type a question (test / fallback)"), {
      target: { value: "my wife is in labor, what should I do" }
    });
    fireEvent.submit(screen.getByPlaceholderText("Type a question (test / fallback)").closest("form")!);

    expect(await screen.findByText("Head promptly to the maternity clinic.")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "Yorùbá" })[0]);
    expect(
      await screen.findByText("Ẹ mú ìyàwó yín lọ sí ilé ìwòsàn lẹ́sẹ̀kẹsẹ̀.")
    ).toBeInTheDocument();
    expect(answer0Calls).toEqual([]);
  });
});
