import test from 'node:test';
import assert from 'node:assert/strict';
import { renderKatexInHtml } from './renderMath';

test('renderKatexInHtml passes plain html through unchanged', () => {
  const html = '<p>Обычный текст <strong>жирный</strong></p>';
  assert.equal(renderKatexInHtml(html), html);
});

test('renderKatexInHtml renders inline math expressions', () => {
  const html = 'Формула <span class="tex-math" data-math="E = mc^2">E = mc^2</span> в тексте';
  const out = renderKatexInHtml(html);
  assert.match(out, /class="katex"/);
  assert.match(out, /class="katex-mathml"/);
  assert.ok(!out.includes('data-math="E = mc^2"'));
});

test('renderKatexInHtml unescapes html attributes like &lt;', () => {
  const html = 'Лимит <span class="tex-math" data-math="x &lt; 0">x &lt; 0</span>';
  const out = renderKatexInHtml(html);
  assert.match(out, /class="katex"/);
});
