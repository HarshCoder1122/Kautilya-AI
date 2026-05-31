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
    return {
      hasArtifact: true,
      artifactType: attrs.type || 'document',
      artifactTitle: attrs.title || 'Analysis',
      artifactFilename: attrs.filename || '',
      artifactSubtype: attrs.subtype || '',
      artifactCode: code.trim(),
      cleanContent: cleanContent || 'Here is the generated artifact:',
    };
  }

  // 3) No artifact
  return { hasArtifact: false, cleanContent: fullContent };
}
