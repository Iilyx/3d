import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  attachCaptureMarkdowns,
  captureOriginOk,
  captureWarning,
  cardCaption,
  documentsFromService,
  freshShots,
  phrasePlan,
  shotTitle,
  phraseRoute,
  filesFromCapture,
  markdownDocName,
  DASHBOARD_ANALYSIS_ASK,
  isDashboardSource,
  matchDashboardFile,
  removeShotAt,
  shotsSource,
  splitPackedSources,
  viewerFrameUrl,
  withShots,
  CAPTURE_MESSAGE,
  type DashboardCard,
} from "./dashboardCapture.ts";

describe("viewerFrameUrl", () => {
  it("defaults to the local preview viewer", () => {
    assert.equal(viewerFrameUrl(""), "http://127.0.0.1:8040/viewer");
  });

  it("appends /viewer when only the origin is set", () => {
    assert.equal(
      viewerFrameUrl("http://127.0.0.1:8040/"),
      "http://127.0.0.1:8040/viewer",
    );
  });
});

describe("filesFromCapture", () => {
  it("keeps png and pdf payloads and drops the rest", () => {
    const files = filesFromCapture({
      type: CAPTURE_MESSAGE,
      files: [
        { name: "экран.png", ext: "png", data_b64: "abc" },
        { name: "Оплаты.pdf", ext: "pdf", data_b64: "def" },
        { name: "notes.txt", ext: "txt", data_b64: "nope" },
        { name: "empty.png", ext: "png", data_b64: "" },
      ],
    });
    assert.deepEqual(
      files.map((file) => file.name),
      ["экран.png", "Оплаты.pdf"],
    );
  });

  it("accepts a message only from the viewer origin", () => {
    const viewer = "http://127.0.0.1:8040/viewer";
    assert.equal(captureOriginOk("http://127.0.0.1:8040", viewer), true);
    assert.equal(captureOriginOk("http://evil.example", viewer), false);
  });
});

describe("phrasePlan", () => {
  it("keeps an open-url only when filters came back", () => {
    assert.equal(phrasePlan({ pull: false }), null);
    const plan = phrasePlan({
      pull: true,
      mrt: "revenue.mrt",
      viewer: "http://127.0.0.1:8040/open?filters=%7B%7D",
      reply: "Сейчас открою.",
      filters: { Month: "Февраль" },
    });
    assert.equal(plan?.filters.Month, "Февраль");
    assert.equal(plan?.mrt, "revenue.mrt");
    assert.equal(plan?.reply, "Сейчас открою.");
  });

  it("does not invent a sentence when the model sent none", () => {
    const plan = phrasePlan({
      pull: true,
      viewer: "http://127.0.0.1:8040/open",
      reply: "  ",
      filters: { Month: "2" },
    });
    assert.equal(plan?.reply, "");
  });
});

describe("phraseRoute", () => {
  it("sends the message when the dashboard service fails", () => {
    assert.equal(phraseRoute(false, { detail: "нет списка фильтров" }), "send");
  });

  it("keeps a real filter miss and a real open", () => {
    assert.equal(
      phraseRoute(true, { pull: false, asked: true, reply: "Нет такого фильтра." }),
      "miss",
    );
    assert.equal(
      phraseRoute(true, {
        pull: true,
        viewer: "http://127.0.0.1:8040/open",
        reply: "Сейчас открою.",
        filters: { Month: "Март" },
      }),
      "open",
    );
    assert.equal(phraseRoute(true, { pull: false }), "send");
  });
});

describe("documentsFromService", () => {
  it("keeps the truncation warning with the table", () => {
    const docs = documentsFromService({
      documents: [
        {
          name: "Table.pdf",
          markdown: "| a |",
          warnings: ["Таблица обрезана: было 80×600, осталось 64×500."],
        },
      ],
    });
    assert.equal(docs.length, 1);
    assert.deepEqual(docs[0].warnings, [
      "Таблица обрезана: было 80×600, осталось 64×500.",
    ]);
    assert.equal(
      captureWarning(docs),
      "Таблица обрезана: было 80×600, осталось 64×500.",
    );
  });

  it("keeps named markdown from the capture route", () => {
    const docs = documentsFromService({
      documents: [
        { name: "screen.png", markdown: "# Экран" },
        { name: " ", markdown: "пустое имя" },
        { name: "Table.pdf", markdown: "  " },
      ],
    });
    assert.deepEqual(docs, [
      { name: "screen.png", markdown: "# Экран", warnings: [] },
    ]);
  });
});

describe("attachCaptureMarkdowns", () => {
  it("stores each png and pdf as its own named markdown", () => {
    const next = attachCaptureMarkdowns(null, [
      { name: "dashboard_20261121.png", markdown: "# Экран\n\nфильтр" },
      { name: "Оплаты_20261121.pdf", markdown: "| a |\n| --- |\n| 1 |" },
    ]);
    assert.equal(next?.parts?.length, 2);
    assert.equal(next?.parts?.[0].name, "Экран дашборда.md");
    assert.equal(next?.parts?.[1].name, "Оплаты_20261121.md");
    assert.match(next?.text || "", /===== Экран дашборда.md =====/);
    assert.match(next?.text || "", /===== Оплаты_20261121.md =====/);
    assert.equal(markdownDocName("Оплаты_20261121.pdf"), "Оплаты_20261121.md");
  });
});

describe("dashboard card shots", () => {
  const card: DashboardCard = {
    viewer: "http://127.0.0.1:8040/open",
    filters: { month: "2", year: "2025" },
    shots: [],
    analyzed: 0,
  };

  it("keeps codes off the card and names a word filter", () => {
    assert.equal(cardCaption({ month: "2", year: "2025" }), "Экран дашборда");
    assert.equal(cardCaption({ month: "Февраль", year: "2025" }), "Февраль · 2025");
  });

  it("sends only shots taken after the last analysis", () => {
    const taken = withShots(card, [
      { name: "screen.png", markdown: "# Экран" },
      { name: " ", markdown: "пусто" },
    ]);
    assert.equal(taken.shots.length, 1);
    const again = withShots(
      { ...taken, analyzed: 1 },
      [{ name: "next.png", markdown: "# Ещё" }],
    );
    assert.deepEqual(
      freshShots(again).map((shot) => shot.name),
      ["next"],
    );
    assert.equal(
      shotTitle(
        "dashboard_20261121_100249.png",
        "## Заголовок\nПоступления за январь 2025 года (с нарастающим итогом)\n",
      ),
      "Поступления за январь 2025 года",
    );
    const packed = shotsSource(freshShots(again));
    assert.match(packed, /===== next.md =====/);
    assert.equal(isDashboardSource("# Данные дашборда\n\n## Экран"), true);
    assert.equal(isDashboardSource("Обычный отчёт"), false);
    assert.deepEqual(
      splitPackedSources(packed).map((doc) => doc.name),
      ["next.md"],
    );
    assert.match(shotsSource(freshShots(again)), /# Ещё/);
  });
});

describe("dashboard landing ask", () => {
  it("asks for a short line and not a writeup", () => {
    assert.match(DASHBOARD_ANALYSIS_ASK, /Длинный разбор в чат не пиши/);
  });
});

describe("matchDashboardFile", () => {
  it("picks the file whose name is the screen title", () => {
    const name = matchDashboardFile(
      [{ name: "Задолженность по налогам и сборам" }],
      [
        { name: "dashboard.mrt", title: "dashboard" },
        {
          name: "Задолженность по налогам и сборам.mrt",
          title: "Задолженность по налогам и сборам",
        },
      ],
    );
    assert.equal(name, "Задолженность по налогам и сборам.mrt");
  });
});

describe("removeShotAt", () => {
  it("removes a captured shot by index and clamps analyzed count", () => {
    const base: DashboardCard = {
      viewer: "/open",
      filters: {},
      shots: [
        { name: "Январь", markdown: "# Данные дашборда\n1", warnings: [] },
        { name: "Февраль", markdown: "# Данные дашборда\n2", warnings: [] },
      ],
      analyzed: 2,
    };
    const next = removeShotAt(base, 0);
    assert.deepEqual(
      next.shots.map((s) => s.name),
      ["Февраль"],
    );
    assert.equal(next.analyzed, 1);
  });
});
