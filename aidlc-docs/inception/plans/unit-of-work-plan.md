# Unit of Work Plan

**Inputs**: `application-design/` (approved: 25 components, 7 services), `stories.md` (24 stories, 9 epics), `execution-plan.md`, README collaboration plan (3 members; Construction work on branches with pull requests)
**Outputs**: `aidlc-docs/inception/application-design/unit-of-work.md`, `unit-of-work-dependency.md` and `unit-of-work-story-map.md`
**Deployment model (fixed)**: one local FastAPI application in one repository. Units of work are **modules** of that one application, not separately deployed services.

---

## Part 1: Decomposition Questions

> **Note:** The team asked the AI to suggest answers. The AI suggested each answer with its reason, and the team took the suggestions; the team confirms them when it approves this plan (see `aidlc-docs/audit.md`, 2026-11-23T18:23:32Z).

Answer each question by writing a letter after the `[Answer]:` tag, or choose **X) Other** and describe what you want. A short reason after the letter records why the team chose it.

### Story Grouping

## Question 1
How should stories and components be grouped into units?

A) By layer: a data and domain unit, an agent unit, then a services and UI unit

B) Feature slices on a shared foundation: one **foundation** unit (database, repositories, LLM client, agent loop, tools, grounding), then one unit per feature group, each including its own service, pages and API routes

C) By feature slices only, with no foundation unit; each slice builds the shared parts it needs first

X) Other (please describe after [Answer]: tag below)

[Answer]: B, the shared agent loop, tools and grounding are needed by three features, so building them once in a foundation unit avoids duplicate work; feature slices then give each owner something a user can try end to end

## Question 2
How many units should there be?

A) 4 units (for example: foundation; import and timeline; organizer and journal; Q&A and evaluation)

B) 5–6 units (for example: foundation; import and timeline; note organizer; journal; Q&A; evaluation and sample data)

C) 7 or more smaller units, about one per epic

X) Other (please describe after [Answer]: tag below)

[Answer]: B, exactly 6 units: U1 Foundation, U2 Import and Timeline, U3 Note Organizer, U4 Daily Journal, U5 Trip Q&A, U6 Sample Data and Evaluation; this matches the epics closely and gives each of the three members two units

### Dependencies and Integration

## Question 3
How should units that depend on each other be built in parallel?

A) The foundation unit defines the interfaces first (repositories, `LLMClient` with `FakeLLMClient`, `ToolRegistry`, grounding). Feature units then build against those interfaces, fakes and sample fixtures, and merge through pull requests once their tests pass

B) Strictly in sequence: a unit starts only after the units it depends on are merged

X) Other (please describe after [Answer]: tag below)

[Answer]: A, with interfaces and FakeLLMClient defined first, feature owners can work in parallel against fakes and fixtures instead of waiting for the real model

## Question 4
Where does the UI for each feature go?

A) In its feature unit: each unit delivers its own pages, htmx fragments and API routes, so a unit is done when a user can use it

B) In one separate UI unit at the end that builds every page

X) Other (please describe after [Answer]: tag below)

[Answer]: A, a unit is only done when a persona can use it, which matches the stories' acceptance criteria

## Question 5
When are the synthetic sample trips (US-21) built? Every other unit needs realistic test data.

A) Early, as part of the unit that builds import, so every later unit can use them as fixtures

B) In a separate evaluation unit, with the evaluation set and script

C) A minimal sample trip early (in the import unit), and the full two trips with all edge cases in the evaluation unit

X) Other (please describe after [Answer]: tag below)

[Answer]: C, a minimal one-day trip in U2 unblocks everyone early as a test fixture; the two full trips with every edge case are built in U6, together with the evaluation set

### Team Alignment

## Question 6
How should unit owners be assigned? (Roles in the README: Ivan runs the agent and commits, Edwin is product lead, Zarif is technical lead.)

A) Assign owners now in `unit-of-work.md`, based on role and interest, with one reviewer for each unit

B) Leave owners as "to be decided" and assign them at the start of Construction

X) Other (please describe after [Answer]: tag below)

[Answer]: A, owners known now let each member start Construction on Nov 25 without another round of planning; each unit also gets a reviewer from the team

## Question 7
If owners are assigned now (Question 6 A), how should they be split?

A) Zarif (technical lead): foundation and journal. Edwin (product lead): note organizer and evaluation (labels and manual review). Ivan: import and timeline, and Q&A

B) Zarif: foundation and Q&A. Edwin: import and timeline, and evaluation. Ivan: note organizer and journal

C) Not applicable (owners decided later)

X) Other (please describe after [Answer]: tag below)

[Answer]: A, the technical lead takes the riskiest technical work (foundation and journal); the product lead takes the organizer and the evaluation labels, which need judgment about categories and correct answers; Ivan takes import, timeline and Q&A, which build on the foundation's tools

### Technical Considerations

## Question 8
When should the team test whether the local model calls tools reliably on every teammate's laptop? (This is a risk in `execution-plan.md`.)

A) As the first task of the foundation unit: a small spike with `qwen3:8b` and one alternative, on every laptop, before feature units depend on the agent loop

B) As a separate, short spike unit before the foundation unit

C) During NFR Requirements for the journal unit

X) Other (please describe after [Answer]: tag below)

[Answer]: A, the agent loop is the biggest risk, so testing tool calling on every laptop first tells the team early whether to switch models

### Business Domain

## Question 9
The journal and Q&A share the tools and the grounding check. Where do those shared pieces belong?

A) In the foundation unit, so both feature units depend on one tested implementation

B) In the journal unit, and the Q&A unit reuses them afterwards

X) Other (please describe after [Answer]: tag below)

[Answer]: A, one tested implementation of the tools and grounding avoids the Q&A unit depending on the journal unit

### Code Organization (greenfield)

## Question 10
How should the code and tests be organized across units?

A) One package `trip_journal/` with the layout in `components.md`. Each unit owns specific modules in it, and tests mirror the units (`tests/unit/`, `tests/agent/`, `tests/api/`, `tests/property/` with files named after each unit's modules)

B) A separate Python package per unit inside the repository (a uv workspace)

X) Other (please describe after [Answer]: tag below)

[Answer]: A, one app and one package are enough for a single local product; a uv workspace would add setup with no benefit

---

## Part 2: Generation Checklist

These steps run only after the answers are analyzed and the team approves this plan.

- [x] Step 1: Define units
  - [x] Name each unit, its purpose, its components (C01–C25) and its modules, following Questions 1, 2, 4 and 9
  - [x] Write each unit's definition of done (stories accepted, tests, ruff, mypy)
  - [x] Record owners and reviewers (Questions 6 and 7)
- [x] Step 2: Document the code organization strategy (greenfield, Question 10)
  - [x] Directory structure and which unit owns which modules
  - [x] Test layout and the shared fixtures, including the sample trips (Question 5)
- [x] Step 3: Define dependencies
  - [x] Build a unit dependency matrix and a build order
  - [x] Describe the integration approach (Question 3) and the model spike (Question 8)
  - [x] Draw the dependency diagram (colorful Mermaid in the README style, with a text alternative)
- [x] Step 4: Map stories to units
  - [x] Assign every story US-01 to US-24 to exactly one primary unit, plus any contributing units
  - [x] Check that no story is unassigned
- [x] Step 5: Validate
  - [x] Unit boundaries match the application design (every component in exactly one unit)
  - [x] No circular dependencies between units
  - [x] Consistency with `execution-plan.md` (per-unit Construction stages)

## Mandatory Unit Artifacts
- [x] Generate `aidlc-docs/inception/application-design/unit-of-work.md` with unit definitions and responsibilities
- [x] Generate `aidlc-docs/inception/application-design/unit-of-work-dependency.md` with dependency matrix
- [x] Generate `aidlc-docs/inception/application-design/unit-of-work-story-map.md` mapping stories to units
- [x] **Greenfield only**: Document code organization strategy in `unit-of-work.md`
- [x] Validate unit boundaries and dependencies
- [x] Ensure all stories are assigned to units
