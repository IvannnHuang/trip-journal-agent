# Unit of Work Story Map

Every story in `stories.md` has **exactly one primary unit**, the unit whose definition of done includes accepting the story. Contributing units provide parts the story relies on.

## Story-to-Unit Map

| Story | Epic | Primary unit | Contributing units | Persona |
|---|---|---|---|---|
| US-01 Import a trip from a JSON file | E1 | **U2** | U1 (repositories, schema) | P1, P2 |
| US-02 Choose the active trip | E1 | **U2** | U1 (settings storage) | P1 |
| US-03 Delete a trip and import a corrected file | E1 | **U2** | U1 (cascading deletes) | P1 |
| US-04 Browse a day's timeline | E2 | **U2** | U1 (base layout) | P1, P2 |
| US-05 See organized reviews on each stop | E2 | **U3** | U2 (timeline stop fragment) | P2 |
| US-06 Run the note organizer | E3 | **U3** | U1 (LLM client, JobRunner) | P2, P1 |
| US-07 Review suggestions one by one | E3 | **U3** | – | P2, P1 |
| US-08 Accept all suggestions for a day | E3 | **U3** | – | P2, P1 |
| US-09 Generate a cited day journal | E4 | **U4** | U1 (AgentLoop, tools, JobRunner, progress fragment) | P1 |
| US-10 See unsupported sentences highlighted | E4 | **U4** | U1 (grounding, highlight macro) | P1 |
| US-11 See how a draft or answer was built | E4 | **U4** | U1 (trace fragment, citation links), U5 (same fragment in chat) | P1, P3 |
| US-12 Edit a journal paragraph | E5 | **U4** | U1 (grounding) | P1 |
| US-13 Regenerate a journal without losing my edits | E5 | **U4** | – | P1 |
| US-14 Ask a question about the trip | E6 | **U5** | U1 (AgentLoop, tools, grounding), U3 (organized ratings, Scenario 3) | P3, P1, P2 |
| US-15 Ask a follow-up question | E6 | **U5** | – | P3, P1 |
| US-16 Be told when the records have no answer | E6 | **U5** | U1 (grounding exemption) | P3, P1 |
| US-17 Turn on place lookup | E7 | **U1** | – | P1 |
| US-18 Set the model and the Ollama address | E7 | **U1** | – | P1, P4 |
| US-19 Keep working when Ollama is not running | E8 | **U1** | U2–U5 (each feature shows the banner) | P1, P3 |
| US-20 Get a clear result when the agent cannot finish | E8 | **U1** | U4, U5 (show the failure in their pages) | P1 |
| US-21 Demo with synthetic sample trips | E9 | **U6** | U2 (minimal trip, import format) | P4 |
| US-22 Build the labelled evaluation set | E9 | **U6** | – | P4 |
| US-23 Run the evaluation script | E9 | **U6** | U2–U5 (services under test) | P4 |
| US-24 Review the demo journals for invented facts | E9 | **U6** | U4 (journals to review) | P4 |

## Stories per Unit

| Unit | Owner | Primary stories | Count | Sizes |
|---|---|---|---|---|
| U1 Foundation | Zarif Karim | US-17, US-18, US-19, US-20 | 4 | M, S, M, S (plus the shared foundation code) |
| U2 Import and Timeline | Ivan Huang | US-01, US-02, US-03, US-04 | 4 | M, S, M, M |
| U3 Note Organizer | Edwin Chen | US-05, US-06, US-07, US-08 | 4 | S, M, M, S |
| U4 Daily Journal | Zarif Karim | US-09, US-10, US-11, US-12, US-13 | 5 | L, M, S, S, M |
| U5 Trip Q&A | Ivan Huang | US-14, US-15, US-16 | 3 | L, S, S |
| U6 Sample Data and Evaluation | Edwin Chen | US-21, US-22, US-23, US-24 | 4 | M, M, M, S |
| **Total** | | | **24** | 10 S, 12 M, 2 L |

**Coverage check**: all 24 stories (US-01 to US-24) are assigned. No story is unassigned, and none has two primary units.

## Epics per Unit

| Epic | Unit(s) |
|---|---|
| E1 Trip Import and Management | U2 |
| E2 Day Timeline | U2 (US-04), U3 (US-05) |
| E3 Note Organizer | U3 |
| E4 Daily Journal and Grounding | U4 (grounding function in U1) |
| E5 Journal Editing | U4 |
| E6 Trip Q&A | U5 |
| E7 Place Lookup and Settings | U1 |
| E8 Reliability | U1 |
| E9 Sample Data and Evaluation | U6 |

## Persona Journeys across Units

| Persona journey (from `stories.md`) | Units in order |
|---|---|
| P1 Lena: import → day → organize → journal → fix flags → edit → regenerate → ask | U2 → U3 → U4 → U5 |
| P2 Marco: import → organize → accept all → fix → reviews on stops | U2 → U3 |
| P3 Jordan: ask → follow up → check source → "not in your records" | U5 (with the shared trace fragment from U1) |
| P4 Team: sample trips → labels → evaluation script → manual review | U6 (over U2–U5) |
