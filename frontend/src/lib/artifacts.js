// Shared artifact parsing — used in BOTH the live streaming path (ChatMain
// updateContent) and the history-hydration path (hydrateHistoryMessage) so an
// artifact that opened in the canvas while streaming re-opens identically after
// a page reload. Previously hydration ignored the saved message text, so the
// "Open in Canvas" button restored an EMPTY canvas (artifactCode was never
// reconstructed) and coder/multi-file projects lost their artifact button
// entirely. Keeping one parser means streaming and reload can never drift.

/** Tiny attribute parser for the `<artifact ...>` / `<file ...>` open tag. */
export function parseAttrs(s) {
  const out = {};
  const re = /([a-zA-Z_:][\w:-]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g;
  let m;
  while ((m = re.exec(s)) !== null) {
    out[m[1].toLowerCase()] = m[2] ?? m[3] ?? m[4] ?? '';
  }
  return out;
}

// "**filename.ext**\n```lang\n...```" style headers that Claude/Emergent coder
// responses emit. 2+ of these (or any explicit <file> tag) → multi-file project.
const FILENAME_HEADER_RE = /(^|\n)[ \t]*(?:\*\*|`|#{1,6}\s+|(?:[Ff]ile|[Ff]ilename|[Pp]ath)\s*[:=]\s*)?[\w./@-]+\.(?:jsx|tsx|js|ts|html|css|py|json|md|vue|svelte|go|rs|java|cpp|c|h|sh|yml|yaml|toml|env)(?:\*\*|`)?[ \t]*\n[ \t]*```/g;

// Map a filename extension → syntax-highlight / preview language.
const _EXT_LANG = { html: 'html', htm: 'html', jsx: 'javascript', tsx: 'typescript',
  js: 'javascript', mjs: 'javascript', ts: 'typescript', css: 'css', json: 'json',
  py: 'python', vue: 'html', svelte: 'html', go: 'go', rs: 'rust', java: 'java',
  cpp: 'cpp', c: 'c', sh: 'bash', yml: 'yaml', yaml: 'yaml' };

/** Decide whether a single <artifact> is really CODE (so the canvas gives it a
 *  live preview + workspace) rather than a prose document. Models often forget
 *  the type= attribute, or wrongly stuff an HTML/React page into a "document"
 *  artifact — which then renders as raw source text. We rescue those by sniffing
 *  the filename extension and the payload. Returns { type, language } or null to
 *  keep the model's stated type. */
function classifyArtifact(declaredType, filename, code) {
  const t = (declaredType || '').toLowerCase().trim();
  // Never touch real structured-data artifacts — they have dedicated viewers.
  if (['excel', 'spreadsheet', 'csv', 'dashboard', 'deck', 'presentation', 'slides'].includes(t)) return null;

  const fname = (filename || '').toLowerCase();
  const ext = (fname.match(/\.([a-z0-9]+)$/) || [])[1] || '';
  const body = (code || '').trim();
  const looksHtml = /^<!doctype html|^<html[\s>]/i.test(body);
  const looksReact = /\b(import|export)\b/.test(body) && /<[A-Za-z][^>]*>/.test(body) && /\breturn\s*\(?\s*</.test(body);
  const codeExt = ['html', 'htm', 'jsx', 'tsx', 'js', 'mjs', 'ts', 'css', 'json', 'py', 'vue', 'svelte'].includes(ext);
  // The master prompt defines type="preview" for self-contained HTML pages/
  // widgets/landing pages — those (and other code-page intents) must ALWAYS
  // render as a live code preview, never as a prose document.
  const codeIntentType = ['preview', 'code', 'html', 'web', 'webpage', 'website',
    'site', 'component', 'app', 'widget', 'ui'].includes(t);

  if (codeExt || looksHtml || looksReact || codeIntentType) {
    const lang = _EXT_LANG[ext] || (looksReact ? 'javascript' : 'html');
    return { type: 'code', language: lang };
  }
  return null; // genuine prose document → leave as-is
}

/**
 * Inspect raw model output and pull out any artifact (multi-file project,
 * <artifact> document/code/spreadsheet, etc.).
 *
 * Returns:
 *   {
 *     hasArtifact, artifactType, artifactTitle, artifactCode,
 *     artifactFilename, artifactSubtype,
 *     cleanContent   // message body with artifact/file payload stripped, for the chat bubble
 *   }
 * For plain text it returns { hasArtifact:false, cleanContent: <input> }.
 */
function _msgText(m) {
  const c = m && (m.artifactCode || m.content);
  return typeof c === 'string' ? c : '';
}

/**
 * Merge a <file> project across the contiguous run of recent assistant turns,
 * so a "continue"/edit turn that only re-sends SOME files still shows the
 * COMPLETE project. We concatenate NEWEST-first (current turn, then the prior
 * project turns walking backwards, stopping at the first assistant message that
 * has no <file> blocks = a topic boundary). Because the canvas parser keeps the
 * FIRST occurrence of each filename, this yields each file's LATEST version
 * plus every earlier file that wasn't re-sent.
 *
 * @param messages  the full message list (chat order, oldest→newest)
 * @param targetId  id of the message whose canvas we're building (null when live)
 * @param liveCode  raw text of the in-flight streaming turn (null when re-opening)
 */
export function mergeProjectCode(messages, targetId, liveCode) {
  const list = Array.isArray(messages) ? messages : [];
  const parts = [];
  let startIdx;
  if (liveCode != null) {
    parts.push(liveCode);
    startIdx = list.length - 1;           // walk all prior history
  } else {
    const idx = list.findIndex(m => m && m.id === targetId);
    if (idx < 0) return liveCode || '';
    parts.push(_msgText(list[idx]));
    startIdx = idx - 1;
  }
  for (let i = startIdx; i >= 0; i--) {
    const m = list[i];
    if (!m) continue;
    if (m.role === 'user') continue;        // skip user turns, keep walking back
    const txt = _msgText(m);
    if (/<file[\s>]/i.test(txt)) parts.push(txt);
    else break;                             // assistant non-project turn = boundary
  }
  return parts.join('\n\n');
}

export function extractArtifact(fullContent) {
  if (!fullContent || typeof fullContent !== 'string') {
    return { hasArtifact: false, cleanContent: fullContent || '' };
  }

  // 1) Multi-file workspace (coder mode)
  const hasFileTags = /<file[\s>]/i.test(fullContent);
  const headerHits = (fullContent.match(FILENAME_HEADER_RE) || []).length;
  if (hasFileTags || headerHits >= 2) {
    const cleanContent = fullContent
      .replace(/<file[\s\S]*?<\/file>/gi, '')
      .replace(/<file[\s\S]*/gi, '')
      .trim();
    return {
      hasArtifact: true,
      artifactType: 'multifile',
      artifactTitle: 'Project Files',
      artifactCode: fullContent,
      cleanContent: cleanContent || 'Here are the project files:',
    };
  }

  // 2) Explicit <artifact ...> document / code / spreadsheet
  const tagMatch = fullContent.match(/<artifact(\s+[^>]+)?>/i);
  if (tagMatch) {
    const openTag = tagMatch[0];
    const attrs = parseAttrs(tagMatch[1] || '');
    const startIndex = tagMatch.index + openTag.length;
    const closeIndex = fullContent.indexOf('</artifact>', startIndex);
    const code = closeIndex >= 0
      ? fullContent.slice(startIndex, closeIndex)
      : fullContent.slice(startIndex);
    const cleanContent = fullContent
      .replace(/<artifact[\s\S]*?<\/artifact>/gi, '')
      .replace(/<artifact[\s\S]*/gi, '')
      .trim();
    // Rescue code/HTML/React pages the model mislabelled (or didn't label) as a
    // document, so they open as code-with-live-preview instead of raw text.
    const reclass = classifyArtifact(attrs.type, attrs.filename, code);
    return {
      hasArtifact: true,
      artifactType: (reclass && reclass.type) || attrs.type || 'document',
      artifactTitle: attrs.title || 'Analysis',
      artifactFilename: attrs.filename || '',
      artifactSubtype: attrs.subtype || '',
      artifactLanguage: (reclass && reclass.language) || '',
      artifactCode: code.trim(),
      cleanContent: cleanContent || 'Here is the generated artifact:',
    };
  }

  // 3) No artifact
  return { hasArtifact: false, cleanContent: fullContent };
}
