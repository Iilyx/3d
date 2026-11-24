/**
 * Visual QA bootstraps (?preview=artifact|flow).
 * No-ops unless the matching query string is present.
 */

import { useEffect, type Dispatch, type SetStateAction } from "react";
import type { ActiveArtifact } from "./ArtifactRail";
import type { ThinkingLine } from "./domain/pipelinePhrases";
import type { Msg, RunResult, SourceDraft } from "./domain/liberTypes";
import {
  appendBotThinking,
  stageLabel,
} from "./domain/runHelpers";

/** Inline stub so ?preview=flow film works without API / figures. */
const PREVIEW_FILM_PNG =
  "data:image/svg+xml," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">
      <rect width="96" height="96" fill="#f4f4f2"/>
      <rect x="14" y="52" width="14" height="28" fill="#2a2a28"/>
      <rect x="34" y="36" width="14" height="44" fill="#5a5a56"/>
      <rect x="54" y="24" width="14" height="56" fill="#2a2a28"/>
      <rect x="74" y="44" width="10" height="36" fill="#8a8a84"/>
    </svg>`,
  );

type SetMsgs = Dispatch<SetStateAction<Msg[]>>;

export function useLiberDevPreviews({
  setMsgs,
  setBusy,
  setSourceDraft,
  setActiveArtifact,
}: {
  setMsgs: SetMsgs;
  setBusy: Dispatch<SetStateAction<boolean>>;
  setSourceDraft: Dispatch<SetStateAction<SourceDraft | null>>;
  setActiveArtifact: Dispatch<SetStateAction<ActiveArtifact | null>>;
}): void {
  // Visual QA: http://127.0.0.1:5173/?preview=artifact
  useEffect(() => {
    if (!/preview=artifact/.test(window.location.search)) return;
    const id = "preview-artifact";
    const result: RunResult = {
      run_id: "source_20261021T082640Z",
      status: "ok",
      downloads: {
        pdf: "/api/runs/source_20261021T082640Z/files/source.pdf",
        docx: "/api/runs/source_20261021T082640Z/files/source.docx",
      },
      preview: {
        title: "Northstar Labs — демо",
        blocks: [
          { type: "heading", level: 1, text: "Итоги квартала" },
          {
            type: "paragraph",
            text: "Рост ускоряется, качество растёт вместе с ним. Это демо Artifact rail.",
          },
          { type: "heading", level: 2, text: "Ключевые метрики" },
          {
            type: "table",
            caption: "KPI",
            headers: ["Метрика", "Q2", "Q3"],
            rows: [
              ["Выручка", "12.4", "14.1"],
              ["NPS", "42", "51"],
            ],
          },
          { type: "heading", level: 2, text: "График" },
          {
            type: "figure",
            id: "cht_01",
            kind: "chart",
            caption: "Распределение бюджета по категориям, %",
            url: "/api/runs/source_20261021T082640Z/figures/cht_01.png",
            chartType: "donut",
            pdfPage: 1,
          },
          { type: "heading", level: 2, text: "Выводы" },
          {
            type: "paragraph",
            text: "Качество растёт вместе с объёмом — смотрите TOC и кнопку PDF на рисунке.",
          },
        ],
      },
      charts_ok: 1,
      figures_ok: 0,
      charts_planned: ["cht_01"],
      figures_planned: [],
      diagrams: [
        {
          id: "dia_01",
          title: "Путь сделки · KPI",
          type: "flowchart",
          mermaid: `flowchart TD
  A(["Лид<br/>340"]):::start --> B["Квалификация<br/>210"]:::process
  B --> C{Бюджет?}:::decision
  C -->|да · 88%| D(["Сделка<br/>185"]):::ok
  C -->|нет · 12%| E["Пауза · 25"]:::warn
  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22
  classDef process fill:#eef3ef,stroke:#6b8f76,color:#1a2e22
  classDef decision fill:#f5e6c8,stroke:#c4a35a,color:#1a2e22
  classDef ok fill:#cfe8d6,stroke:#5a9a6e,color:#1a2e22
  classDef warn fill:#f0d4d0,stroke:#b56a5e,color:#1a2e22
`,
        },
        {
          id: "dia_02",
          title: "Склад · поток",
          type: "flowchart",
          mermaid: `flowchart LR
  A["Приёмка · 1 240 шт"]:::start --> B["Размещение · 1 180"]:::process
  B --> C{Брак?}:::decision
  C -->|да · 5%| D["Возврат · 60"]:::warn
  C -->|нет · 95%| E["Отгрузка · 1 120"]:::ok
  classDef start fill:#dce8df,stroke:#6b8f76,color:#1a2e22
  classDef process fill:#eef3ef,stroke:#5a7a64,color:#1a2e22
  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22
  classDef ok fill:#cfe6d4,stroke:#3d7a4a,color:#1a2e22
  classDef warn fill:#f0ddd8,stroke:#a85a4a,color:#1a2e22
`,
        },
        {
          id: "dia_03",
          title: "Согласование договоров",
          type: "flowchart",
          mermaid: `flowchart TD
  A["Черновик · 42"]:::data --> B["Юрист"]:::process
  B --> C{ОК?}:::decision
  C -->|да| D["Подпись · 38"]:::ok
  C -->|нет · 4| E["Правки"]:::warn
  E --> B
  classDef data fill:#d9e6f0,stroke:#4a6f8c,color:#1a2e22
  classDef process fill:#eef3ef,stroke:#5a7a64,color:#1a2e22
  classDef decision fill:#f3e6c8,stroke:#b8893a,color:#1a2e22
  classDef ok fill:#cfe6d4,stroke:#3d7a4a,color:#1a2e22
  classDef warn fill:#f0ddd8,stroke:#a85a4a,color:#1a2e22
`,
        },
      ],
      diagrams_ok: 3,
      diagrams_planned: ["dia_01", "dia_02", "dia_03"],
      output_mode: "report",
      warnings: [],
    };
    setMsgs([
      {
        id: "preview-user",
        role: "user",
        text:
          "Собери отчёт по демо: таблица KPI, один line-график, спокойная палитра atelier, без лишней воды и без выдуманных цифр — только Source.",
        chips: ["демо", "палитра: atelier", "графики: ≤2"],
        attachment: {
          title: "northstar_demo.md",
          text: "# Source\n\nДемонстрационный файл для вкладки Source.\n",
          fileName: "northstar_demo.md",
        },
      },
      {
        id,
        role: "bot",
        text:
          "Собрал демо-отчёт: структура, таблица и ключевой график.\n\nОткройте карточку ниже — полный документ в панели.",
        result,
      },
    ]);
    setSourceDraft({
      title: "northstar_demo.md",
      text: "# Source\n\nДемонстрационный файл для вкладки Source.\n",
      fileName: "northstar_demo.md",
    });
    // Julius QA: cards stay in chat; rail opens only on «Открыть»
  }, [setMsgs, setSourceDraft, setActiveArtifact]);

  // Visual QA: http://127.0.0.1:5173/?preview=deck-busy — live ThinkingFold + DeckBuildCard
  useEffect(() => {
    if (!/preview=deck-busy/.test(window.location.search)) return;
    const id = "preview-deck-busy";
    const stages = [
      "slides_queued",
      "slides_llm",
      "slides_diagrams",
      "slides_render",
      "slides_pptx",
    ] as const;
    const stageToSlides = (k: string) => k.replace(/^slides_/, "");
    let i = 0;
    let thinking: ThinkingLine[] = [];
    let thinkingStartedAt = Date.now();
    let thinkingStageKey: string | undefined;
    let thinkingStageAt = Date.now();
    const tick = () => {
      const key = stages[i % stages.length];
      const slidesStage = stageToSlides(key);
      const draft = appendBotThinking(
        {
          id,
          role: "bot",
          text: "Собираю презентацию…",
          pending: true,
          pendingStage: key,
          thinkingMode: "presentation",
          thinking,
          thinkingStartedAt,
          thinkingStageKey,
          thinkingStageAt,
          result: {
            run_id: "preview-deck-busy",
            status: "ok",
            downloads: {
              pdf: "/api/runs/source_20261021T082640Z/files/source.pdf",
            },
            preview: {
              title: "Marketing QBR",
              blocks: [
                { type: "heading", level: 1, text: "Quarterly business review" },
              ],
            },
            charts_ok: 0,
            figures_ok: 0,
            charts_planned: [],
            figures_planned: [],
            warnings: [],
            slides_status: "running",
            slides_stage: slidesStage,
          },
        },
        key,
        null,
      );
      thinking = draft.thinking || [];
      thinkingStartedAt = draft.thinkingStartedAt || thinkingStartedAt;
      thinkingStageKey = draft.thinkingStageKey;
      thinkingStageAt = draft.thinkingStageAt || thinkingStageAt;
      setBusy(true);
      setMsgs([
        {
          id: "preview-deck-busy-user",
          role: "user",
          text: "Сделай презентацию по отчёту.",
        },
        draft,
      ]);
      i += 1;
    };
    tick();
    const t = window.setInterval(tick, 1600);
    return () => {
      window.clearInterval(t);
      setBusy(false);
    };
  }, [setMsgs, setBusy]);

  // Visual QA: http://127.0.0.1:5173/?preview=deck — real IR + twin PNGs (structure/Present)
  useEffect(() => {
    if (!/preview=deck(?:-busy)?/.test(window.location.search)) return;
    if (/preview=deck-busy/.test(window.location.search)) return;
    const id = "preview-deck";
    const runId =
      new URLSearchParams(window.location.search).get("run") ||
      "source_20261030T083857Z";
    let cancelled = false;
    (async () => {
      let slidePngs: string[] = [];
      let deck: RunResult["deck"] = null;
      let downloads: Record<string, string> = {
        pptx: `/api/runs/${runId}/files/deck.pptx`,
        deck_pdf: `/api/runs/${runId}/files/deck.pdf`,
      };
      try {
        const g = await fetch(`/api/runs/${encodeURIComponent(runId)}/slides`);
        const body = await g.json().catch(() => ({}));
        if (Array.isArray(body.slide_pngs)) slidePngs = body.slide_pngs;
        if (body.deck) deck = body.deck;
        if (body.downloads && typeof body.downloads === "object") {
          downloads = { ...downloads, ...body.downloads };
        }
      } catch {
        /* keep stubs */
      }
      if (cancelled) return;
      const result: RunResult = {
        run_id: runId,
        status: "ok",
        output_mode: "presentation",
        downloads,
        preview: {
          title: "Marketing QBR",
          blocks: [
            { type: "heading", level: 1, text: "Quarterly business review" },
            {
              type: "paragraph",
              text: "Демо: Present · DnD reorder · дубль/удаление.",
            },
          ],
        },
        charts_ok: 0,
        figures_ok: 0,
        charts_planned: [],
        figures_planned: [],
        warnings: [],
        slides_status: "ok",
        slide_pngs: slidePngs,
        deck: deck ?? undefined,
      };
      setMsgs([
        {
          id: "preview-deck-user",
          role: "user",
          text: "Собери презентацию QBR: два слайда, спокойная палитра.",
        },
        {
          id,
          role: "bot",
          text: "Готово — презентация и PDF twin. Откройте карточку, чтобы править слайды.",
          result,
        },
      ]);
      setActiveArtifact({
        kind: "report",
        msgId: id,
        tab: "presentation",
        title: "Marketing QBR",
      });
    })();
    return () => {
      cancelled = true;
    };
  }, [setActiveArtifact, setMsgs]);

  // Visual QA: http://127.0.0.1:5173/?preview=flow — SSE phase 2A craft (ETA + substeps + skip)
  useEffect(() => {
    if (!/preview=flow/.test(window.location.search)) return;
    const stages = [
      "queued",
      "llm",
      "charts",
      "charts",
      "inject",
      "latex",
      "docx",
      "ok",
    ] as const;
    const id = "preview-flow";
    let i = 0;
    let thinking: ThinkingLine[] = [];
    let thinkingStartedAt = Date.now();
    let thinkingStageKey: string | undefined;
    let thinkingStageAt = Date.now();
    const tick = () => {
      const idx = i % stages.length;
      if (idx === 0 && i > 0) {
        thinking = [];
        thinkingStartedAt = Date.now();
        thinkingStageKey = undefined;
        thinkingStageAt = Date.now();
      }
      const stage = stages[idx];
      const chartBeat = idx === 2 ? "cht_01" : idx === 3 ? "cht_02" : null;
      const detail = chartBeat;
      setBusy(stage !== "ok");
      if (stage === "ok") {
        setMsgs([
          {
            id: "preview-user",
            role: "user",
            text: "Intent · preview flow",
          },
          {
            id,
            role: "bot",
            text: "Готово · preview — структура ясна, отчёт собран.",
            pending: false,
            thinking,
            thinkingStartedAt,
            thinkingElapsedSec: Math.max(
              0,
              Math.round((Date.now() - thinkingStartedAt) / 1000),
            ),
            craftSkipped: { photos: "IMAGE_API_BASE_URL empty" },
            craftFilm: [
              {
                id: "cht_01",
                kind: "chart",
                url: PREVIEW_FILM_PNG,
              },
            ],
            craftRecap: "Собрано за 0:12 · PDF · DOCX · 1 график",
            result: {
              run_id: "preview-flow",
              status: "ok",
              downloads: {},
              charts_ok: 0,
              figures_ok: 0,
              charts_planned: [],
              figures_planned: [],
              warnings: [],
            },
          },
        ]);
      } else {
        const craftSubsteps =
          stage === "charts"
            ? [
                {
                  id: "cht_01",
                  label: "cht_01",
                  status: (chartBeat === "cht_01" ? "active" : "done") as
                    | "active"
                    | "done",
                },
                ...(chartBeat === "cht_02"
                  ? [
                      {
                        id: "cht_02",
                        label: "cht_02",
                        status: "active" as const,
                      },
                    ]
                  : []),
              ]
            : [];
        const draft = appendBotThinking(
          {
            id,
            role: "bot",
            text: stageLabel(stage, detail),
            pending: true,
            pendingStage: stage,
            pendingDetail: detail,
            thinking,
            thinkingStartedAt,
            thinkingStageKey,
            thinkingStageAt,
            craftSubsteps,
            craftSkipped: { photos: "IMAGE_API_BASE_URL empty" },
            etaSec: stage === "charts" ? 38 : stage === "latex" ? 55 : null,
            craftFilm:
              stage === "charts" ||
              stage === "inject" ||
              stage === "latex" ||
              stage === "docx"
                ? [
                    {
                      id: "cht_01",
                      kind: "chart",
                      url: PREVIEW_FILM_PNG,
                    },
                    ...(chartBeat === "cht_02" ||
                    stage === "inject" ||
                    stage === "latex" ||
                    stage === "docx"
                      ? [
                          {
                            id: "cht_02",
                            kind: "chart" as const,
                            url: PREVIEW_FILM_PNG,
                          },
                        ]
                      : []),
                  ]
                : [],
          },
          stage,
          detail,
        );
        thinking = draft.thinking || [];
        thinkingStartedAt = draft.thinkingStartedAt || thinkingStartedAt;
        thinkingStageKey = draft.thinkingStageKey;
        thinkingStageAt = draft.thinkingStageAt || thinkingStageAt;
        setMsgs([
          {
            id: "preview-user",
            role: "user",
            text: "Intent · preview flow",
          },
          draft,
        ]);
      }
      i += 1;
    };
    tick();
    const t = window.setInterval(tick, 1400);
    return () => window.clearInterval(t);
  }, [setMsgs, setBusy]);

  // Visual QA: http://127.0.0.1:5173/?preview=craft-error — frozen + hint
  useEffect(() => {
    if (!/preview=craft-error/.test(window.location.search)) return;
    setBusy(false);
    setMsgs([
      {
        id: "preview-craft-err-user",
        role: "user",
        text: "Собери отчёт по Source.",
      },
      {
        id: "preview-craft-err",
        role: "bot",
        text: "Сборка остановилась на TeX.",
        pending: false,
        pendingStage: "latex",
        thinkingMode: "report",
        craftFrozen: true,
        craftSkipped: { photos: "IMAGE_API_BASE_URL empty" },
        craftSubsteps: [
          { id: "cht_01", label: "cht_01", status: "done" },
          { id: "cht_02", label: "cht_02", status: "done" },
        ],
        errorHint: "TeX: проверь таблицу (tabularx) · открой log",
        thinking: [
          { id: "t1", text: "Читаю Source", stageKey: "llm" },
          { id: "t2", text: "Верстаю текст", stageKey: "inject" },
          { id: "t3", text: "Печатаю PDF", stageKey: "latex" },
        ],
        thinkingElapsedSec: 12,
        error: "latexmk failed",
      },
    ]);
  }, [setMsgs, setBusy]);
}
