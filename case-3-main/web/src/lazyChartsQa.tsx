/** Shared lazy ChartsQa — keep out of the default App chunk. */

import { lazy } from "react";

export const ChartsQa = lazy(() =>
  import("./ChartsQa").then((m) => ({ default: m.ChartsQa })),
);
