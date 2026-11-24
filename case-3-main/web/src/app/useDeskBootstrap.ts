/** Health + deck-theme bootstrap for Liber desk (out of App). */

import { useEffect, type Dispatch, type SetStateAction } from "react";
import type { Health } from "../domain/liberTypes";
import type { DeckThemePackInfo } from "../deckStyle";

type Deps = {
  setHealth: Dispatch<SetStateAction<Health | null>>;
  setMaxCharts: Dispatch<SetStateAction<number>>;
  setMaxDiagrams: Dispatch<SetStateAction<number>>;
  setMaxDiagramsCap: Dispatch<SetStateAction<number>>;
  setMaxImages: Dispatch<SetStateAction<number>>;
  setForbidImages: Dispatch<SetStateAction<boolean>>;
  setDeckPacks: Dispatch<SetStateAction<DeckThemePackInfo[]>>;
};

export function useDeskBootstrap({
  setHealth,
  setMaxCharts,
  setMaxDiagrams,
  setMaxDiagramsCap,
  setMaxImages,
  setForbidImages,
  setDeckPacks,
}: Deps) {
  useEffect(() => {
    let cancelled = false;
    fetch("/api/health")
      .then(async (r) => {
        if (!r.ok) throw new Error(`health ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        setHealth(data);
        const d = data?.defaults;
        if (d && typeof d.max_charts === "number") setMaxCharts(d.max_charts);
        if (d && typeof d.max_diagrams === "number")
          setMaxDiagrams(d.max_diagrams);
        if (d && typeof d.max_diagrams_cap === "number" && d.max_diagrams_cap > 0)
          setMaxDiagramsCap(d.max_diagrams_cap);
        if (d && typeof d.max_images === "number") {
          setMaxImages(d.max_images);
          if (
            d.max_images > 0 &&
            (data.image_api_configured || data.kandinsky_configured)
          ) {
            setForbidImages(false);
          }
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealth({
            ok: false,
            docker_ok: false,
            playwright_ok: false,
            vision_configured: false,
            kandinsky_configured: false,
            docker_error: "Сервер временно недоступен",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [
    setHealth,
    setMaxCharts,
    setMaxDiagrams,
    setMaxDiagramsCap,
    setMaxImages,
    setForbidImages,
  ]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/deck-themes")
      .then(async (r) => {
        if (!r.ok) throw new Error(`deck-themes ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (cancelled) return;
        const packs = data?.packs;
        if (Array.isArray(packs) && packs.length) {
          setDeckPacks(packs as DeckThemePackInfo[]);
        }
      })
      .catch(() => {
        /* keep FALLBACK_DECK_PACKS */
      });
    return () => {
      cancelled = true;
    };
  }, [setDeckPacks]);
}

