/** Shared lazy chunk for PDF first-page preview (rail + report). */

import { lazy } from "react";

export const PdfFirstPage = lazy(() =>
  import("./PdfFirstPage").then((m) => ({ default: m.PdfFirstPage })),
);
