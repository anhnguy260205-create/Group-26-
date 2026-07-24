# Group-26 — Feature Spec (Web App)

> **Everyone cares for the patient. We watch over the caregiver.**

A caregiver wellbeing web app. Each day takes one minute: a quick check-in on mood,
sleep, and care hours. From that, plus an optional AI companion chat and a one-line
journal, the app tracks the caregiver's stress, **predicts where it's heading**, and steps
in *before* burnout — with support, suggestions, real local resources, and a crisis
safety net.

**Not a medical or diagnostic tool.** It is a support-and-signposting companion. All
wording says so.

---

## Positioning (read first)

- **Persona: family caregivers.** Sharp, chronic, under-served pain; strong emotional
  resonance; clear B2B2C payer later (employer caregiver-benefits, insurers, health
  systems, eldercare orgs). We are not "a mood app for everyone."
- **Our differentiator is predict-and-prevent, not chat.** Mood trackers and AI chatbots
  are a crowded space. What sets us apart is the **Caregiver Digital Twin**: forecasting
  stress from the last several days and intervening *before* the peak. Lean on this.
- **Localized & socially useful.** Region-aware resource finder (Singapore / Malaysia)
  and a responsible crisis safety net make the social value concrete.

---

## Core MVP (24–48h, demo-ready)

### 1. Login
Simple account so data persists per caregiver. (Firebase Auth or email/password.)

### 2. Daily Check-in — *the most important feature*
One minute a day.
- **Mood:** 😀 Good · 🙂 Okay · 😔 Drained · 😭 Barely holding on
- **A few quick questions:** hours slept · hours spent caregiving · did you get any time
  for yourself?
- **Output: a daily Stress Score** (0–100) combining mood + sleep + care load + me-time.

### 3. AI Companion (LLM chat)
Warm, non-clinical support.
> "I'm really about to break down today."
> → "Many people caring long-term for family feel this way. Do you want to tell me what
>    happened today?"
- Empathetic, validating, and it can reference the caregiver's recent check-ins/journal
  for context. **Support, not therapy.**

### 4. Journal
One line a day: *what happened today?*
- AI auto-summary across entries, e.g. *"Your biggest stress in the last 3 days has been
  night-time caregiving."*
- Feeds the Digital Twin.

### 5. Burnout Dashboard (trends)
The "proof it's working" screen.
- Trend lines for Stress ↑↓, Sleep ↑↓, Mood ↑↓ over time.
- **Burnout Risk** indicator (Low / Moderate / High) from sustained patterns
  (e.g. 7 days of high stress + low sleep + low mood).
- When risk is high, concrete suggestions: *rest 30 min today · ask a relative for help ·
  contact a hospital medical social worker.*

### 6. Resource Finder (region-aware)
- **Singapore:** AIC (Agency for Integrated Care), Caregivers Alliance Limited (CAL),
  SOS / Samaritans of Singapore (crisis).
- **Malaysia:** Befrienders, Malaysian Mental Health Association (MMHA).
- ⚠️ **Verify current hotline numbers/links before the demo** — put live, correct details
  in the app; don't ship stale contacts.

---

## Differentiators (what wins the award)

### ⭐ Caregiver Digital Twin — predictive stress (headline innovation)
From several days of sleep, mood, care hours, and journal sentiment, the AI **forecasts
the next few days' stress trend** and proactively nudges the caregiver to schedule rest or
ask for help *before* risk climbs.
> *"Your stress has been rising, mainly from longer night-time caregiving. The next two
>    days look heavy — consider handing off one night this week."*
- "Predict & prevent" shows AI value far better than a reactive chatbot.
- **Demo note:** predictions need history — **seed 7+ days of demo data** so the twin has
  something to forecast on stage.

### ⭐ Caregiver Crisis Detection (high social value — handle responsibly)
If the user expresses crisis language (e.g. self-harm / not wanting to live), the app
**breaks out of normal chat** and instead:
- responds with care, not a generic reply;
- encourages reaching out to a trusted person and seeking professional help;
- surfaces local crisis resources immediately (SOS in SG, Befrienders in MY).
- **Guardrails:** never claims to diagnose or treat; makes no promises about
  confidentiality; positioned purely as support + signposting. This is a safety feature,
  not a medical one.

### AI enhancements (layer onto the above)
- **Emotion analysis** of journal/chat: *Emotion: Frustrated · Stress: High · Burnout
  Risk: Moderate.*
- **Daily AI suggestions** (non-medical): *walk 10 min · drink water · breathe · sleep
  earlier tonight.*
- **AI Weekly Summary:** *"Over the past 7 days: Sleep ↓, Stress ↑, Mood ↓ — the main
  driver appears to be longer night-time caregiving."*

---

## Optional bonus (only if core is done)

### Quick Pulse Check (rPPG)
A "take a 20-second pulse reading" button that enriches a check-in via the webcam. The
existing rPPG code already supports this. **Self-report stays the reliable core;** rPPG is
a wow-factor extra that gracefully falls back to manual if the signal is noisy.

---

## AI layer — Microsoft Foundry

Route all LLM calls (companion chat, journal summary, emotion analysis, weekly summary,
digital-twin narration, crisis wording) through **Microsoft Foundry** — the backend is
already wired for it (`backend/app/llm.py`), with Anthropic-direct and templated-text
fallbacks. This keeps **Best Use of Microsoft Stack** in play at no extra cost.

- Keep safety-critical logic **rule-based** (crisis keyword detection, burnout-risk
  thresholds) so it can't fail on a flaky network; the LLM only *phrases*.
- Optional later: **RAG** over a caregiving knowledge base for grounded, cited advice;
  **Foundry Evaluators** to validate outputs — great roadmap/trust story.

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React + Tailwind, installable **PWA** (feels like a phone app) |
| Backend | **FastAPI** (already scaffolded) |
| Database | PostgreSQL (or Firebase for auth + quick data) |
| AI | **Microsoft Foundry** (via existing `llm.py`); rule-based safety logic |

**Reuse what's built:** the teammate's FastAPI + React scaffold, SQLite/DB layer, and the
Foundry-wired `llm.py` all carry over. The main change is swapping the rPPG-first flow for
a check-in-first flow (and keeping rPPG as the optional pulse check).

---

## Reliability / fallback

- **LLM unreachable →** templated text; safety logic (crisis, burnout risk) is rule-based
  and never depends on the LLM.
- **rPPG noisy/denied →** it's optional; the check-in is the source of truth anyway.
- **Crisis detection →** keyword/rule trigger first (deterministic), LLM only softens the
  wording — must fire even offline.

---

## Judging rubric map

| Weight | Criterion | What carries it |
|---|---|---|
| 30% | Innovation & creativity | Caregiver Digital Twin (predict & prevent) + responsible crisis detection |
| 20% | Problem–solution fit | Sharp caregiver persona; 1-minute daily check-in that busy caregivers will actually do |
| 20% | Technical execution | Prediction from real trend data + Foundry AI + optional rPPG pulse |
| 20% | Presentation quality | Burnout dashboard visuals; a real caregiver story; the "it saw it coming" moment |
| 10% | Entrepreneurship | Beachhead + B2B2C payer + localized social value + Microsoft/compliance narrative |

---

## Suggested 24–48h build order

1. **Foundry hello-world + DB + login** wired end-to-end (do this first — external deps).
2. **Daily Check-in → Stress Score** (the data engine).
3. **Burnout Dashboard** with **seeded 7-day demo data** (so trends + twin have something).
4. **AI Companion chat** (Foundry).
5. **Digital Twin prediction** + **Crisis Detection** (the two award features).
6. **Journal + AI summaries**, then **Resource Finder**.
7. Lock code, rehearse the golden-path demo, record a backup video.

---

## Team ownership (suggested)

- **Dylan** — Check-in flow, Burnout Dashboard, Resource Finder UI
- **Jordan** — Data model + Stress Score + Digital Twin prediction logic (optional rPPG)
- **Rayden** — AI layer (Foundry wiring, companion, summaries, crisis detection rules)
- **Kim** — Journal + AI summaries, pitch narrative & demo script
