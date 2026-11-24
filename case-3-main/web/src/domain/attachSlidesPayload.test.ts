/** attachSlidesPayload — status-ok without twin PNGs must hydrate for chat/rail. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  attachSlidesPayload,
  needsSlidesHydrate,
} from "./attachSlidesPayload";
import type { RunResult } from "./liberTypes";

function base(partial: Partial<RunResult> = {}): RunResult {
  return {
    run_id: "r1",
    status: "ok",
    downloads: { pptx: "/api/runs/r1/files/x.pptx" },
    charts_ok: 0,
    figures_ok: 0,
    charts_planned: [],
    figures_planned: [],
    warnings: [],
    slides_status: "ok",
    ...partial,
  };
}

describe("attachSlidesPayload", () => {
  it("merges slide_pngs + deck so preview is not empty", () => {
    const out = attachSlidesPayload(base({ slide_pngs: [] }), {
      slide_pngs: ["/api/runs/r1/slides/png/slide_01.png"],
      deck: { version: 1, slides: [{ id: "s1", layout: "title_panel" }] },
      downloads: { deck_pdf: "/api/runs/r1/files/x_deck.pdf" },
      deck_pdf_mode: "lo",
    });
    assert.equal(out.slide_pngs?.length, 1);
    assert.equal(out.deck?.slides?.length, 1);
    assert.equal(out.downloads.deck_pdf, "/api/runs/r1/files/x_deck.pdf");
    assert.equal(out.deck_pdf_mode, "lo");
  });

  it("does not wipe existing pngs with empty payload list", () => {
    const out = attachSlidesPayload(
      base({ slide_pngs: ["/keep.png"] }),
      { slide_pngs: [] },
    );
    assert.deepEqual(out.slide_pngs, ["/keep.png"]);
  });
});

describe("needsSlidesHydrate", () => {
  it("true when slides ok / pptx but no twin thumbs", () => {
    assert.equal(needsSlidesHydrate(base()), true);
    assert.equal(
      needsSlidesHydrate(
        base({
          slide_pngs: ["/a.png"],
          deck: { slides: [{ id: "s1", layout: "title" }] },
        }),
      ),
      false,
    );
    assert.equal(
      needsSlidesHydrate(
        base({ slides_status: "running", downloads: {} }),
      ),
      false,
    );
  });

  it("true when pngs exist but deck IR missing (chat live twin)", () => {
    assert.equal(
      needsSlidesHydrate(base({ slide_pngs: ["/a.png"] })),
      true,
    );
  });
});

describe("prefersLiveChatHero", () => {
  it("live when deck has slides; else png fallback", async () => {
    const { prefersLiveChatHero } = await import("./chatDeckHero");
    assert.equal(prefersLiveChatHero(null), false);
    assert.equal(prefersLiveChatHero(undefined), false);
    assert.equal(prefersLiveChatHero({ slides: [] }), false);
    assert.equal(
      prefersLiveChatHero({ slides: [{ id: "s1", layout: "title" }] }),
      true,
    );
  });
});
