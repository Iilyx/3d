/** Single-kick slides job helpers. */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { DEFAULT_DECK_STYLE, slidesAutoKickPayload } from "../deckStyle";
import {
  slidesJobInFlight,
  slidesJobNeedsKick,
  slidesJobTerminal,
} from "./runHelpers";

describe("slidesKick helpers", () => {
  it("needs kick only when idle (not already 202)", () => {
    assert.equal(slidesJobNeedsKick({ slides_status: "idle" }), true);
    assert.equal(slidesJobNeedsKick({ slides_status: null }), true);
    assert.equal(slidesJobNeedsKick({ slides_status: "running" }), false);
    assert.equal(slidesJobNeedsKick({ slides_status: "queued" }), false);
    assert.equal(slidesJobNeedsKick({ slides_status: "starting" }), false);
    assert.equal(slidesJobNeedsKick({ slides_status: "ok" }), false);
    assert.equal(
      slidesJobNeedsKick({
        slides_status: "idle",
        downloads: { pptx: "/x.pptx" },
      }),
      false,
    );
  });

  it("auto kick marks itself so Stop is not cleared", () => {
    const body = slidesAutoKickPayload(DEFAULT_DECK_STYLE);
    assert.equal(body.kick_source, "api_auto");
    assert.equal(body.theme_pack, "atelier");
  });

  it("inFlight / terminal cover Windows poll wait", () => {
    assert.equal(slidesJobInFlight("running"), true);
    assert.equal(slidesJobInFlight("queued"), true);
    assert.equal(slidesJobInFlight("idle"), false);
    assert.equal(slidesJobTerminal("ok"), true);
    assert.equal(slidesJobTerminal("error"), true);
    assert.equal(slidesJobTerminal("running"), false);
  });
});
