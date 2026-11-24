## Mermaid `diagrams` (Liber UI & PDF/DOCX) — **default ON**

`{{MAX_DIAGRAMS}}` is a **ceiling**. Liber renders these into high-resolution graphics for PDF and DOCX reports, as well as showing them in the Artifact rail. Showcase the product: when the budget is ≥ 1, **prefer emitting 1 useful diagram** over leaving `"diagrams": []`.

### Default-on rule (mandatory when {{MAX_DIAGRAMS}} ≥ 1)

Emit **at least one** diagram if Source/Intent has **any** of:

- numbered / bulleted steps, stages, phases, pipeline;
- decision / branch language («если… иначе», да/нет, согласование);
- roles / actors / departments / org;
- system parts / architecture / data flow;
- cause→effect or non-numeric timeline;
- document outline with **≥3** topical sections (then a simple flowchart of sections is OK).

Only skip (`"diagrams": []`) when **all** hold: budget is 0, **or** Intent explicitly says «без схем» / «без Mermaid», **or** Source is pure numbers/table with **no** process/roles/structure to map.

Numbers alone → `charts`, not diagrams. But numbers **plus** a process → charts **and** one diagram.

Prefer **1** strong diagram over 2 thin ones. Two only when Source clearly has two different structures (e.g. process + roles).

### Type whitelist (strict)

`flowchart`, `sequence`, `mindmap`, `timeline`, `stateDiagram`.

First line of `mermaid` **must** match type:

| type | first line starts with |
|------|-------------------------|
| flowchart | `flowchart LR` or `flowchart TD` (not `graph` — write `flowchart`). For Liber deck: TD if ≤5 steps (fills height); LR for wide pipelines |
| sequence | `sequenceDiagram` |
| mindmap | `mindmap` |
| timeline | `timeline` |
| stateDiagram | `stateDiagram-v2` or `stateDiagram` |

Mini-examples (labels only from Source):

```text
flowchart TD
  A[Заявка · 340]:::start --> B{Проверка}:::decision
  B -->|да · 88%| C[Отгрузка · 1 090]:::ok
  B -->|нет · 12%| D[Отказ]:::warn
  classDef start fill:…,stroke:…,color:#1a2e22
  classDef process fill:…,stroke:…,color:#1a2e22
  classDef decision fill:…,stroke:…,color:#1a2e22
  classDef ok fill:…,stroke:…,color:#1a2e22
  classDef warn fill:…,stroke:…,color:#1a2e22
  classDef data fill:…,stroke:…,color:#1a2e22
```

(Example numbers must come from Source — never invent. Fill/stroke hex come from the Liber diagram colors table in the user message — do not invent a second palette.)

```text
sequenceDiagram
  participant M as Менеджер
  participant J as Юрист
  M->>J: договор
  J-->>M: ok
```

### Node colors (model owns styles — mandatory for flowchart)

The **model** assigns roles and colors via Mermaid `:::class` + `classDef` (or `style NodeId …`). Liber does not invent colors on the client.

| Role class | Use when |
|------------|----------|
| `start` | entry / trigger |
| `process` | action / step |
| `decision` | `{ромб}` branch |
| `ok` | success / approve / done |
| `warn` | reject / return / risk |
| `data` | document / system / data |

Rules for colors:

- Every flowchart node gets a `:::role` (or `style`) — do **not** leave all nodes the same default fill.
- Styles go on **`classDef name fill:…`** — never `class name fill:…` (that is invalid). Assign nodes with `class A,B process` or `:::process`.
- `color:#1a2e22` text on every classDef.
- **Hex values:** only from the **Liber diagram colors** table in the user message (live palette). Do not hardcode a second palette.
- **No purple / violet / neon** fills (no `#7c3aed`, `#a855f7`, glow). Soft editorial only.
- sequence / mindmap / timeline: color when Mermaid allows; flowchart is the showcase for roles.

### Rules

- `mermaid`: plain source, **no** ``` fences.
- Prefer flat flowcharts (Liber visual editor). `subgraph` is OK for big org/hierarchy charts — Liber flattens them when editing by hand.
- Edges: `-->` (and labeled `-->|…|`); avoid `A --> B --> C` chains on one line — one edge per line.
- **Node ids ASCII** (`A`, `step1`); Russian only inside `[]` / `()` / participant aliases — never invent actors/steps not in Source.
- `title`: short Russian (≤80 chars) for Liber tab «Схема» — **specific** (not «Универсальная схема процесса»).
- Ids prefer `dia_NN`. Unique across figures + charts + diagrams.
- **TeX slots:** In LaTeX prose, place `%CASE3_DIAG:dia_NN%` on its own line beside the related process / architecture description. Do not put raw Mermaid syntax in LaTeX. If you omit the slot, Liber will automatically place the diagram before the conclusion.
- **Annotated flow (numbers on structure):** when Source ties a number/% to a step/entity/branch, put it **in the node or edge label** — prefer short two-line `["Заявка<br/>820"]` or `Заявка · 820`. Digits **verbatim from Source only**. **Keep text short:** ≤4 words in the title line; **do not** stuff role codes (SDR/SE/AE/Legal) into the node label — roles are optional on edges or omitted. Edge labels short: `62%`, `нет бюджета · 95`. Prefer 1 key metric per node; do **not** dump a full chart series. Charts still own series; diagram owns structure + KPI callouts.
- **No `click` / links** in Mermaid.

### Anti-slop (mandatory)

Forbidden as the whole diagram:

- Linear chains of empty stages: `Начало → Этап 1 → Этап 2 → … → Завершение`.
- Labels that are only `Этап N` / `Шаг N` / `Step N` without Source nouns.
- Title like «Универсальная схема…» when Source has a real process name.

Required when Source allows:

- Decision language → `{ромб}` + labeled `|да|` / `|нет|` (or Source words).
- Named actors/roles → put them on nodes or use `sequenceDiagram`.
- Parallel / fork language → two outgoing edges from one node (not a fake linear list).
