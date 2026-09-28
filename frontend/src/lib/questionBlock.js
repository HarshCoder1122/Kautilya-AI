/* Shared parsing for the interactive ```question / ```ask block.
 *
 * The model doesn't always emit a clean fenced block — it often writes the
 * fence inline right after a sentence ("…send them.```question { … }"), which
 * CommonMark then does NOT treat as a code block, so the raw JSON would leak
 * into the chat as text. So we DON'T rely on markdown parsing: we scan the raw
 * message text ourselves, brace-match the JSON object, and strip it out. The
 * card is rendered docked above the composer (Claude-style), not inline. */

/** Normalize one question object → {question, options, allowCustom, multiSelect}
 * or null if it has no question text or no options. */
function _normalizeQuestion(item) {
  if (!item || typeof item !== "object") return null;
  const question = String(item.question || item.prompt || item.title || item.label || "").trim();
  const rawOpts = Array.isArray(item.options) ? item.options
    : Array.isArray(item.choices) ? item.choices : [];
  const options = rawOpts
    .map((o) => (typeof o === "string"
      ? { label: o.trim(), description: "" }
      : { label: String(o.label ?? o.text ?? o.value ?? "").trim(),
          description: String(o.description ?? o.detail ?? "").trim() }))
    .filter((o) => o.label);
  if (!question || options.length === 0) return null;
  return {
    question,
    options,
    allowCustom: item.allowCustom !== false, // default on
    multiSelect: Boolean(item.multiSelect || item.multi),
  };
}

/** Tolerant parse of the question JSON. Returns { questions: [...], skipLabel }
 * (a list of 1+ normalized questions — the model may ask several per task), or
 * null if nothing valid. Accepts both the single-question shape
 * `{question, options}` and the multi shape `{questions: [ {question,options}, … ]}`. */
export function parseQuestion(raw) {
  const src = (raw || "").trim();
  if (!src) return null;
  let data;
  try {
    data = JSON.parse(src);
  } catch {
    const a = src.indexOf("{");
    const b = src.lastIndexOf("}");
    if (a < 0 || b <= a) return null;
    try { data = JSON.parse(src.slice(a, b + 1)); } catch { return null; }
  }
  if (!data || typeof data !== "object") return null;
  const list = Array.isArray(data.questions) ? data.questions
    : Array.isArray(data.fields) ? data.fields : [data];
  const questions = list.map(_normalizeQuestion).filter(Boolean).slice(0, 6);
  if (questions.length === 0) return null;
  return {
    questions,
    intro: String(data.intro || data.title || "").trim(),
    skipLabel: typeof data.skipLabel === "string" ? data.skipLabel : "Skip",
  };
}

/** Locate a ```question/```ask block anywhere in `text`, brace-match its JSON,
 * and return { code, cleaned } where `code` is the JSON string (or null) and
 * `cleaned` is `text` with the whole block (fence + JSON + closing fence)
 * removed. Position-independent and tolerant of a missing closing fence
 * (truncated / still-streaming output). */
export function extractQuestionBlock(text) {
  if (!text || typeof text !== "string") return { code: null, cleaned: text || "" };

  const fence = /```[ \t]*(?:question|ask)\b/i;
  const fm = text.match(fence);
  if (!fm) return { code: null, cleaned: text };

  const markerStart = fm.index;
  const braceStart = text.indexOf("{", markerStart + fm[0].length);
  if (braceStart < 0) {
    // Marker but no JSON yet (mid-stream) — hide everything from the marker on.
    return { code: null, cleaned: text.slice(0, markerStart).trim() };
  }

  // Brace-match the JSON object, ignoring braces inside strings.
  let depth = 0, inStr = false, esc = false, end = -1;
  for (let i = braceStart; i < text.length; i++) {
    const ch = text[i];
    if (inStr) {
      if (esc) esc = false;
      else if (ch === "\\") esc = true;
      else if (ch === '"') inStr = false;
    } else if (ch === '"') inStr = true;
    else if (ch === "{") depth++;
    else if (ch === "}") { depth--; if (depth === 0) { end = i; break; } }
  }

  if (end < 0) {
    // Unterminated (truncated/streaming) — take the rest as the code.
    return { code: text.slice(braceStart).trim(), cleaned: text.slice(0, markerStart).trim() };
  }

  const code = text.slice(braceStart, end + 1);
  let tail = end + 1;
  const closeFence = text.slice(tail).match(/^[ \t]*\r?\n?[ \t]*```/);
  if (closeFence) tail += closeFence[0].length;
  const cleaned = (text.slice(0, markerStart) + text.slice(tail)).trim();
  return { code, cleaned };
}
