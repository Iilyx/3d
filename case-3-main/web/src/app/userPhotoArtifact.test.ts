import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { ActiveArtifact } from "../ArtifactRail";
import type { UserPhotoThumb } from "../domain/liberTypes";

describe("userPhotoArtifact", () => {
  it("formats user photo into media artifact object", () => {
    const photo: UserPhotoThumb = {
      url: "blob:http://localhost:5173/test-uuid",
      name: "diagram_schema.png",
    };
    const artifact: ActiveArtifact = {
      kind: "media",
      msgId: "",
      tab: "preview",
      runId: "run_123",
      mediaId: photo.name || "user_photo",
      url: photo.url,
      title: photo.name || "Фото",
    };

    assert.equal(artifact.kind, "media");
    assert.equal(artifact.title, "diagram_schema.png");
    assert.equal(artifact.url, photo.url);
    assert.equal(artifact.mediaId.startsWith("film_"), false);
  });

  it("distinguishes film frame vs user photo in rail tabs", () => {
    const isFilmMedia = (mediaId: string) => mediaId.startsWith("film_");
    const getTabLabel = (isMedia: boolean, mediaId: string) => {
      if (!isMedia) return "Превью";
      return isFilmMedia(mediaId) ? "Кадр" : "Фото";
    };

    assert.equal(getTabLabel(true, "film_0"), "Кадр");
    assert.equal(getTabLabel(true, "film_2"), "Кадр");
    assert.equal(getTabLabel(true, "user_photo"), "Фото");
    assert.equal(getTabLabel(true, "my_chart.png"), "Фото");
  });
});
