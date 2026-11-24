import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./app/App";
import { installWorkspaceFetch } from "./app/workspaceId";
import { ConfirmProvider } from "./ConfirmModal";
/* Direct imports — Vite @import inlining was serving a stale CSS bundle. */
import "./styles/tokens.css";
import "./styles/shell.css";
import "./styles/chat.css";
import "./styles/chat-thinking.css";
import "./styles/chat-diagrams.css";
import "./styles/chat-charts-qa.css";
import "./styles/composer.css";
import "./styles/deck.css";
import "./styles/rail.css";
import "./styles/presentation.css";
import "./styles/modals.css";
import "katex/dist/katex.min.css";

installWorkspaceFetch();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ConfirmProvider>
      <App />
    </ConfirmProvider>
  </StrictMode>,
);
