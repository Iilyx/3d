/**
 * Renders LaTeX math expressions inside HTML fragments using KaTeX.
 * Replaces <span class="tex-math" data-math="..."> elements with KaTeX rendered markup.
 */

import katex from 'katex';

function decodeHtmlAttr(str: string): string {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

export function renderKatexInHtml(html: string): string {
  if (!html || !html.includes('tex-math')) {
    return html;
  }
  return html.replace(
    /<span class="tex-math" data-math="([^"]*)">([\s\S]*?)<\/span>/g,
    (_match, attrMath, inner) => {
      const raw = decodeHtmlAttr(attrMath || inner || '');
      try {
        return katex.renderToString(raw, {
          throwOnError: false,
          displayMode: false,
        });
      } catch {
        return `<span class="tex-math tex-math-fallback">${inner}</span>`;
      }
    }
  );
}
