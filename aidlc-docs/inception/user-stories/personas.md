# Personas: Trip Journal Agent

These personas are **invented**. They are built from the user types in `docs/vision.md` (story plan Questions 2 and 3) and contain no teammate's real habits, names or trip data. Each persona lists the stories they take part in; the full matrix is at the end of this file.

---

## P1: Lena Zhou, the Trip Logger (primary persona)

| Attribute | Detail |
|---|---|
| **Age and work** | 31, UX researcher at a mid-size company |
| **Travel pattern** | 3–4 multi-day trips a year, usually 3–6 days each, mostly city trips, often with her partner Jordan (P3) |
| **What she records** | A tracking app on her phone logs 8–15 stops a day and exports JSON. She takes about 200 photos a day and types 10–20 short notes in the moment |
| **Note style** | Fragments typed while walking: "broth great, too salty, 4/5", "queue 40 min — skip next time". She grew up bilingual and often mixes Mandarin and English in one note ("这家 dumplings 超好吃, get the pork ones") |
| **Comfort with technology** | High. She is comfortable exporting a file, opening a localhost page and following a README to start Ollama, but she does not want to write code or edit JSON by hand |
| **Laptop** | A 16 GB laptop with no dedicated GPU |

**Goals**
- Turn each day into a readable journal in a few minutes, not an evening
- Keep her own wording where she has rewritten something
- Find details later ("where was that dumpling place on day 2?") without scrolling through hundreds of items

**Frustrations today**
- Her notes never get matched to the places they describe, so they lose their meaning after a week
- Generic chatbots she tried wrote pleasant prose about things that never happened
- She does not want her location history uploaded to a cloud service

**What success looks like for her**
- A cited draft for each day that she only edits lightly, and that never invents a place, time or rating
- Regenerating a draft never touches the paragraphs she rewrote

**Quote**: "I have all the data. I just never have the evening it takes to turn it into something I'd read again."

**Uses**: trip import, day timeline, note organizer, daily journal, journal editing, Q&A, place lookup, settings

**Stories**: US-01, US-02, US-03, US-04, US-06, US-07, US-08, US-09, US-10, US-11, US-12, US-13, US-14, US-15, US-16, US-17, US-18, US-19, US-20

---

## P2: Marco Reyes, the Food and Place Reviewer

| Attribute | Detail |
|---|---|
| **Age and work** | 38, high-school chemistry teacher; runs a small food blog as a hobby |
| **Travel pattern** | 2–3 food-focused trips a year, typically 4 days, planned around restaurants and markets |
| **What he records** | Rates almost every meal and sight from 1 to 5, in a consistent but terse pattern: dish, rating, one tip ("pork bun 5/5, cash only", "temple 3/5 — go before 9, tour buses") |
| **Comfort with technology** | Medium. He can import a file a friend helped him export, but anything that looks like raw data or a log puts him off |

**Goals**
- Get his ratings and tips turned into clean per-place reviews (dish, rating, tip) attached to the right stop
- Correct the organizer quickly when it gets a category or a stop wrong, without retyping notes
- Reuse the reviews later when he writes a blog post

**Frustrations today**
- He copies ratings from his notes app into a spreadsheet by hand after every trip
- When two notes describe the same meal, he loses track of which tip belongs to which place

**What success looks like for him**
- After one review pass, every rated stop on the day timeline shows its dish, rating and tip
- He can accept a whole day of correct suggestions at once and fix only the few wrong ones

**Quote**: "I already wrote the review. I just wrote it in six words on a sidewalk."

**Uses**: trip import, note organizer, day timeline (organized reviews), Q&A for "what did I rate highest?"

**Stories**: US-01, US-04, US-05, US-06, US-07, US-08, US-14

---

## P3: Jordan Price, the Trip Companion

| Attribute | Detail |
|---|---|
| **Age and work** | 33, nurse working rotating shifts; Lena's partner |
| **Travel pattern** | Travels with Lena on most trips; takes a few photos on their shared camera and no notes |
| **How he uses the app** | On **Lena's laptop**, with or without Lena there, in the same chat panel (story plan Question 4). He never imports or organizes anything |
| **Comfort with technology** | Low to medium. He is happy typing a question into a chat box, does not know what a stop id or a JSON file is, and does not want to learn |

**Goals**
- Ask loose, plain-language questions ("what was the name of the temple on day 3?", "where did we have that spicy fish?") and get a short, correct answer
- Ask a follow-up ("and what did we do after that?") without repeating the context
- Trust the answer, or be told plainly that the records do not say

**Frustrations today**
- He has to wait for Lena to scroll through her phone to settle "what was that place called?"
- He distrusts confident answers from chatbots that turned out to be made up

**What success looks like for him**
- An answer in under half a minute, with a link he can click to see where it came from
- "That's not in your records" instead of a guess

**Quote**: "I don't need the whole journal. I just want to know what that place was called."

**Uses**: Q&A chat panel and the citations and tool-call list it shows

**Stories**: US-11, US-14, US-15, US-16, US-19

---

## P4: The Project Team as Evaluator

| Attribute | Detail |
|---|---|
| **Who** | The three-person project team, in the role of evaluating the product before the demo (story plan Questions 2 and 10). Not an end user |
| **Context** | Must show the vision's success metrics on data that contains no real personal information, on the team's slowest demo laptop |
| **Comfort with technology** | High. Runs `uv run` commands, reads evaluation output and pytest reports |

**Goals**
- Repeatable sample trips that exercise every feature, including mixed-language notes and questions with no answer
- A labelled set of notes and questions to measure accuracy against
- One command that reports grounding rate, note-organization accuracy and Q&A accuracy
- A clear, recorded check that the demo journals contain no invented stop names, times or ratings

**Frustrations to avoid**
- Results that change from run to run with no way to tell why
- Accidentally committing real trip data

**Quote**: "If we can't measure it on the sample trips, we can't claim it in the demo."

**Uses**: sample data, evaluation script, manual review checklist, settings (model choice)

**Stories**: US-18, US-21, US-22, US-23, US-24

---

## Persona-to-Story Matrix

`●` = primary persona of the story · `○` = also takes part

| Story | P1 Lena (logger) | P2 Marco (reviewer) | P3 Jordan (companion) | P4 Team (evaluator) |
|---|---|---|---|---|
| US-01 Import a trip | ● | ○ | | |
| US-02 Choose the active trip | ● | | | |
| US-03 Delete and re-import a trip | ● | | | |
| US-04 Browse a day's timeline | ● | ○ | | |
| US-05 See organized reviews on each stop | | ● | | |
| US-06 Run the note organizer | ○ | ● | | |
| US-07 Review suggestions one by one | ○ | ● | | |
| US-08 Accept all suggestions for a day | ○ | ● | | |
| US-09 Generate a cited day journal | ● | | | |
| US-10 See unsupported sentences highlighted | ● | | | |
| US-11 See how a draft or answer was built | ● | | ○ | |
| US-12 Edit a journal paragraph | ● | | | |
| US-13 Regenerate without losing my edits | ● | | | |
| US-14 Ask a question about the trip | ○ | ○ | ● | |
| US-15 Ask a follow-up question | ○ | | ● | |
| US-16 Be told when the records have no answer | ○ | | ● | |
| US-17 Turn on place lookup | ● | | | |
| US-18 Set the model and Ollama address | ● | | | ○ |
| US-19 Keep working when Ollama is not running | ● | | ○ | |
| US-20 Get a clear result when the agent cannot finish | ● | | | |
| US-21 Demo with synthetic sample trips | | | | ● |
| US-22 Build the labelled evaluation set | | | | ● |
| US-23 Run the evaluation script | | | | ● |
| US-24 Review demo journals for invented facts | | | | ● |
