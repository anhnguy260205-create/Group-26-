# Care Capacity — Product Redesign (one loop)

> **Everyone cares for the patient. We watch over the caregiver.**

## The one idea

The product is **one loop**, not a set of features. Every screen is a stage of this
loop, or it gets cut.

```
Check-in  →  Capacity Engine  →  Forecast  →  Explain  →  Action  →  Outcome  →  (Next Check-in)
```

Read it as a sentence: *the caregiver checks in → we turn that into a Capacity number →
we forecast where it's heading → we explain the caregiving reason → we mobilise one
concrete piece of help → the next day we show it worked → and the loop repeats.*

**Capacity, not stress.** We track how much the caregiver has *left to give* (0 = depleted,
100 = full), because that is how a caregiver actually experiences the problem. Internally
it is `100 − stress`; externally it is the whole product.

## What makes this a *caregiver* app (not a stress app)

A generic stress app tracks one person. A caregiver app tracks **you in relation to the
person you care for, and the network around you both.** That relationship is the moat.
Every stage below carries a caregiver-only hook — marked 🩺.

| A stress app has… | We have… (🩺 caregiver-only) |
|---|---|
| your mood | your mood **+ how the person you care for is doing today** |
| "did you sleep" | "were you **woken to give care** last night, how many times" |
| "take a break" | "**ask your sister to cover Tuesday night**" / "book respite via AIC" |
| a solo diary | a **care network** that actions mobilise |

If you strip the care recipient and the network out, the app collapses back into "everyone
with stress." They are the spine — keep them in every stage.

---

## The loop, stage by stage

### 0. Onboarding (once) — establishes "this is a caregiver app" in the first 60 seconds
Collected once, colours everything after.
- **Who do you care for?** relationship (parent / spouse / child / other). 🩺
- **Their condition** (dementia / stroke / cancer / disability / frailty) → sets vocabulary
  and which resources appear. 🩺
- **Care intensity** — rough hours/day, living together? 🩺
- **Your support network** — names of people who *could* help (sister, spouse, neighbour).
  This list is what the Action stage draws on. 🩺
- **Region** (Singapore / Malaysia) → resource + crisis set.

### 1. Check-in — the input (≤ 1 minute, ≤ 6 questions)
- **You:** mood — 😀 Good · 🙂 Okay · 😔 Drained · 😭 Barely holding on.
- **Night care:** woken to give care last night? how many times? 🩺 *(a stress app never asks this)*
- **Care load today:** hours + "harder than usual?" 🩺
- **The person you care for:** How was [Mom] today — better / same / worse? 🩺 *(the two-body signal — your core differentiator)*
- **Backup:** did anyone help / could you step away? (yes/no) 🩺
- *(optional)* 20-second **rPPG pulse** — passive signal, so capacity isn't 100% self-report.
- Also, if yesterday had an Action: **"Did you manage [ask sister to cover a night]?"** → feeds Outcome.

### 2. Capacity Engine — the number
Turns the check-in (plus optional pulse) into **Capacity 0–100**.
- Depletion model: short sleep, night wakeups, long care hours, no backup, no me-time, low
  mood, and **the recipient getting worse** all pull capacity down.
- Deterministic and offline-safe; pulse nudges it when present, self-report is the floor.
- This is today's headline number on Home.

### 3. Forecast — where it's heading
- Projects Capacity for the next 2–3 days from recent history, with a confidence band.
- **Already built** (`backend/app/twin.py`) — just present it as capacity (invert the sign)
  and surface it, don't leave it buried.

### 4. Explain — why (so it doesn't feel like the AI is guessing)
- Names the **driver** in caregiving terms: night waking · **[Mom] declining** · no backup ·
  long care hours · no time for yourself · isolation. 🩺
- Shows a **confidence** figure.
- Driver detection already exists (`twin._detect_driver`); make the recipient-trend and
  night-wakeups first-class drivers.

### 5. Action — one concrete move that mobilises the network 🩺 *(the stage you're missing)*
Not "take a rest." One specific, caregiver-shaped action tied to the driver:
- **"Ask [sister] to cover Tuesday night"** → generates the actual message to send.
  *(uses the onboarding network + your existing `delegation.py`)*
- **"Book 2h respite via AIC"** (region resource).
- **"Message the hospital medical social worker about [Mom]'s worsening."**
- Each card: **Done · Skip.** Status is stored — this is what closes the loop.

### 6. Outcome — proof it worked
- Next day, compare capacity and **attribute it**: *"You handed off Tuesday night → slept 6h
  → Capacity +11."* 🩺
- This is the "it saw it coming, you acted, it recovered" moment. Without it the loop is open.

### 7. Next Check-in
- Loop repeats; tomorrow's check-in asks whether yesterday's Action happened, feeding
  Outcome and adherence.

---

## Home = the whole loop on one screen

Not a dashboard of modules. One vertical story:

```
Today's Capacity            71
Forecast (next 3 days)      63 → 49   ⚠️ Risk increasing
Why?                        driver: night care · confidence 86%
Today's action              Ask your sister to cover Tue night   [Done] [Skip]
Yesterday's outcome         You protected 30 min → Capacity +6
Quick check-in →
```

Support lives off to the side, summoned only when needed — never in the main spine:
- **AI Companion** — trimmed to 3 buttons (I'm overwhelmed · I need advice · Talk to someone).
- **Crisis** — deterministic keyword breakout to local lines (SOS / Befrienders).
- **Resources** — appear only at high risk or crisis, not as permanent nav. 🩺

---

## Data model (minimal — this is what makes the loop causal)

```
CareContext        recipient_relationship, recipient_condition, care_hours_per_day,
                   lives_together, region
NetworkMember      name, relationship            # who the Action stage can mobilise
Checkin            date, mood, hours_slept, night_wakeups, care_hours, harder_than_usual,
                   recipient_trend(better/same/worse), someone_helped, had_me_time,
                   capacity(0-100)
Action             date, driver, text, target(network member / service),
                   status(pending/done/skipped)      # ← the table you don't have yet
Outcome (derived)  capacity before vs after a `done` Action → the attribution line
```

`Checkin` extends today's `StressReading(source="checkin")`. `Action` is new — it's the
spine you're missing. `Outcome` is computed, not stored.

---

## Keep / Fold / Cut (against current code)

**Keep** — Check-in (`CheckinPage`), Forecast + driver (`twin.py`), Crisis
(`companion.py` keyword path), rPPG (`rppg.js`) now promoted from bonus to the passive
capacity signal.

**Fold** — Journal → one optional line inside Check-in. Weekly summary → an *Insights*
strip, not its own page. Emotion analysis → an internal signal, no standalone screen. AI
Companion → 3 buttons. Breathing intervention → one *type* of Action, not a separate flow.

**Cut / rebuild** — the task-list Dashboard as Home (Home becomes the loop). The scattered
6-item nav.

**Build new** — the `Action` table + Done/Skip, and the Outcome attribution. Wire
`delegation.py` (already written, currently unused) into the Action stage — it's your most
caregiver-specific asset.

---

## Backend endpoints (map to existing + new)

- `POST /checkin` → returns `capacity` (exists; add capacity + new fields). 
- `GET /forecast` → capacity forecast + band (exists as `/stress/forecast`, reframe).
- `GET /explain` → driver + confidence (exists inside forecast, expose cleanly).
- `GET /action/today` → one action for today's driver, drawing on network (**new**, uses
  `delegation.py`).
- `POST /action/{id}/status` → done / skipped (**new**).
- `GET /outcome` → capacity delta attributed to the last done action (**new**).
- Support: `POST /companion/chat`, `GET /resources`, crisis path — all exist.

---

## Demo golden path (seed this)

Dementia mother, night waking escalating over the week:
1. Days 1–4: Capacity slides 78 → 71 → 63 → 55. Driver: **night care**. 🩺
2. Forecast on Day 4: "next two days 49, then 42 — ⚠️ heading for a crash."
3. Action: **"Ask your sister to cover Fri & Sat nights."** → user taps **Done**.
4. Days 5–6: Capacity recovers 55 → 66 → 74.
5. Outcome: **"You handed off two nights → slept → Capacity +19. Your action worked."**

One clean arc: **sense → predict → explain → act → recover.** That's the pitch.

`backend/seed_demo.py` must produce exactly this declining-then-recovering curve so the
story is visible on stage.

---

## Build order (highest story-per-hour first)

1. **`Action` table + Done/Skip** — the missing spine. Wire `delegation.py`.
2. **Outcome attribution** — closes the loop; this is the demo's magic moment.
3. **Home = the loop on one screen** — reuse the forecast/risk cards you already have.
4. **Capacity reframe** — `100 − stress` everywhere; rename the number in the UI.
5. **Check-in caregiver fields** — night wakeups + recipient trend (the two-body signal).
6. **Seed the golden-path curve**; trim nav; fold Journal/Weekly/Emotion.

Everything above is either moving existing code or two small new pieces (Action, Outcome).
You are not rebuilding — you are giving the parts a spine.
