import { Brain, Code, ChartBar, ArrowSquareOut, Play, Pause, Copy, Check, ArrowsClockwise, SpeakerHigh, StopCircle, CalendarCheck, VideoCamera, Link, Crown, Lightning } from "@phosphor-icons/react";
import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import { ThinkingTokens } from "./ThinkingTokens";
import { ReActSteps } from "./ReActSteps";
import { ToolResultCards } from "./ToolResultCards";
import { ttsAPI } from "../../lib/api";
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { MermaidDiagram, SvgBlock } from "./MermaidDiagram";
import { extractQuestionBlock } from "../../lib/questionBlock";

const CALENDAR_RE = /https?:\/\/(calendar\.google\.com|meet\.google\.com|zoom\.us|teams\.microsoft\.com)[^\s\)\]"<]*/g;

function linkifyContent(text) {
  if (!text) return text;
  // Skip URLs that are already part of a markdown link/image:
  //   [text](url)  or  ![alt](url)  or  <url>
  // We only autolink BARE URLs that appear after whitespace / start-of-string.
  // Using negative lookbehind to make sure we don't match if preceded by '](' (markdown link target) or '="' (HTML attribute)
  return text.replace(
    /(^|[\s(])(?<!\]\()(?<!=")(https?:\/\/[^\s\)\]"<>]+)/g,
    (full, pre, url) => `${pre}[${url}](${url})`
  );
}

function splitCrammedEmojis(content) {
  if (!content || typeof content !== 'string') return content;
  const emojiRegexGlobal = /(?:✅|❌|⭐|🔹|🔸|🔷|🔶|🔵|🔴|🟢|🟡|🟠|🟣|🟤|🎯|📌|📍|👉|➡|✨|⚡|🔥|💡|🚨|ℹ|✔|✖|☑)/gu;
  const emojiRegexSingle = /(?:✅|❌|⭐|🔹|🔸|🔷|🔶|🔵|🔴|🟢|🟡|🟠|🟣|🟤|🎯|📌|📍|👉|➡|✨|⚡|🔥|💡|🚨|ℹ|✔|✖|☑)/u;

  const lines = content.split('\n');
  let inCodeBlock = false;

  const processedLines = lines.map(line => {
    if (line.trim().startsWith('```')) {
      inCodeBlock = !inCodeBlock;
      return line;
    }
    if (inCodeBlock) return line;
    
    // Skip splitting if the line looks like part of a markdown table
    if (line.includes('|')) return line;

    const matches = line.match(emojiRegexGlobal);
    if (matches && matches.length >= 2) {
      const firstEmojiMatch = line.match(emojiRegexSingle);
      if (firstEmojiMatch) {
        const firstIdx = firstEmojiMatch.index;
        const preamble = line.substring(0, firstIdx).trim();
        const afterPreamble = line.substring(firstIdx);

        const splitSection = afterPreamble.replace(emojiRegexGlobal, '\n- $&');
        return preamble ? `${preamble}\n${splitSection.trim()}` : splitSection.trim();
      }
    }
    return line;
  });

  return processedLines.join('\n');
}


/** Normalize an href so plain `youtube.com/abc` doesn't get treated as a
 * path relative to ai.revealiq.in. Adds https:// when the model forgets it. */
function normalizeHref(href) {
  if (!href || typeof href !== 'string') return '#';
  const s = href.trim();
  if (!s) return '#';
  // Allow legitimately scheme-d / in-app / anchor / mailto / tel
  if (/^(https?:|ftp:|mailto:|tel:|sms:|#|\/)/i.test(s)) return s;
  if (s.startsWith('//')) return `https:${s}`;
  // Bare domain like "youtube.com/abc" → add https://
  if (/^[a-z0-9.-]+\.[a-z]{2,}(\/|$)/i.test(s)) return `https://${s}`;
  return s;
}

function extractSources(text) {
  const match = text.match(/sources:\s*(\[[\s\S]*?\])/);
  if (!match) return { sources: null, cleanText: stripToolTags(text) };

  try {
    const sources = JSON.parse(match[1]);
    const cleanText = stripToolTags(text.replace(/sources:\s*\[[\s\S]*?\]/, '').trim());
    return { sources, cleanText };
  } catch (e) {
    return { sources: null, cleanText: stripToolTags(text) };
  }
}

// Strip raw agent-loop tool tokens so they don't leak into the rendered
// message. The agent-loop already executes the tool and emits its own
// structured result; the raw "[TOOL_NAME: args]" token is internal plumbing.
// IMPORTANT: only include tokens the agent_loop ACTUALLY emits. Generic
// names (CODE, EMAIL, PYTHON, MATH, etc.) would falsely match legit
// markdown like `[Python: Real Python tutorial](url)` and strip the link.
const TOOL_NAMES = [
  // Original list
  'SEARCH',
  'CALCULATE',
  'CALENDAR_LIST', 'CALENDAR_CREATE', 'CALENDAR_DELETE',
  'GMAIL_LIST', 'GMAIL_SEND', 'GMAIL_READ',
  'RUN_PYTHON', 'FETCH_URL',
  'WHATSAPP_SEND', 'SLACK_POST', 'HUBSPOT_CREATE_CONTACT',
  'INTEGRATION', 'MAP_SEARCH', 'ROUTE_PLAN', 'GST_INVOICE',
  // Kautilya Computer — persistent per-session file tools (agent_loop_service.py)
  'FILE_WRITE', 'FILE_READ', 'FILE_LIST',
  // Kautilya Computer — live browser tools (agent_loop_service.py)
  'BROWSE', 'BROWSE_CLICK', 'BROWSE_TYPE', 'BROWSE_SCROLL',
  // Coder and other agent commands
  'IMAGE', 'WEATHER', 'NEWS', 'STOCK', 'PREDICT_STOCK', 'CRYPTO', 'MOVIE', 'QUOTE', 'FACT', 'DEFINE',
  'TRANSLATE', 'CONVERT', 'CURRENCY', 'WIKI', 'HOROSCOPE', 'RECIPE', 'MAP', 'ROUTE',
  'CREATE_FILE', 'WRITE_FILE', 'EDIT_FILE', 'READ_FILE', 'LIST_FILES', 'LIST_DIR', 'TREE',
  'DELETE_FILE', 'MOVE_FILE', 'MAKEDIRS', 'SHELL_EXEC', 'FETCH_DOCS', 'INSTALL_SKILL',
  'SELF_OPTIMIZE', 'HISTORY', 'FINISH'
].join('|');

function findBalancedCommand(text, startIndex) {
  let count = 0;
  let inQuote = false;
  let quoteChar = null;
  let escaped = false;
  
  for (let i = startIndex; i < text.length; i++) {
    const char = text[i];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (char === '\\') {
      escaped = true;
      continue;
    }
    if (char === "'" || char === '"') {
      if (!inQuote) {
        inQuote = true;
        quoteChar = char;
      } else if (char === quoteChar) {
        inQuote = false;
        quoteChar = null;
      }
    }
    if (!inQuote) {
      if (char === '[') {
        count++;
      } else if (char === ']') {
        count--;
      }
      if (count === 0) {
        return i;
      }
    }
  }
  return -1;
}

function stripToolTags(text) {
  if (!text || typeof text !== 'string') return text;

  const toolNamesPattern = new RegExp(`^\\[(?:${TOOL_NAMES})(?::|\\])`);
  let result = '';
  let pos = 0;

  while (pos < text.length) {
    const nextBracket = text.indexOf('[', pos);
    if (nextBracket === -1) {
      result += text.substring(pos);
      break;
    }

    result += text.substring(pos, nextBracket);
    const remaining = text.substring(nextBracket);
    const match = remaining.match(toolNamesPattern);

    if (match) {
      const endIdx = findBalancedCommand(text, nextBracket);
      if (endIdx !== -1) {
        pos = endIdx + 1;
        continue;
      }
      // Unterminated tool tag (model ran out of max_tokens mid-JSON).
      // Drop everything from `[TOOL:` to end-of-text so the raw payload
      // doesn't leak into the chat bubble as garbage markdown.
      break;
    }

    result += '[';
    pos = nextBracket + 1;
  }

  return result
    .replace(/^[ \t]+$/gm, '')                       // trailing whitespace on lines
    // ReAct scaffolding — case-sensitive so we don't mangle prose like "Action:"
    .replace(/^\s*(OBSERVATION|THOUGHT|ACTION|FINAL ANSWER)\s*:.*$/gm, '')
    .replace(/\n{3,}/g, '\n\n')                      // collapse blank-line runs
    .trim();
}

function removeIndentedCodeBlocks(text) {
  if (!text || typeof text !== 'string') return text;
  
  const lines = text.split('\n');
  let inCodeBlock = false;
  
  const processedLines = lines.map(line => {
    if (line.trim().startsWith('```')) {
      inCodeBlock = !inCodeBlock;
      return line;
    }
    if (inCodeBlock) {
      return line;
    }
    
    // Check if line has 4 or more leading spaces
    const leadingSpaces = line.match(/^ {4,}/);
    if (leadingSpaces) {
      const rest = line.substring(leadingSpaces[0].length);
      // If it starts with list item marker or blockquote, keep it
      const isListOrQuote = /^[ \t]*(?:[-*+>]|\d+\.\s|\d+\)\s)/.test(rest);
      if (isListOrQuote) {
        return line;
      }
      return rest;
    }
    return line;
  });
  
  return processedLines.join('\n');
}

function unindentMathBlocks(text) {
  if (!text || typeof text !== 'string') return text;
  
  const lines = text.split('\n');
  let inMathBlock = false;
  let inCodeBlock = false;
  
  const processedLines = lines.map(line => {
    const trimmed = line.trim();
    
    if (trimmed.startsWith('```')) {
      inCodeBlock = !inCodeBlock;
      return line;
    }
    
    if (inCodeBlock) {
      return line;
    }
    
    if (trimmed.startsWith('$$')) {
      if (trimmed.endsWith('$$') && trimmed.length > 2) {
        return trimmed;
      }
      inMathBlock = !inMathBlock;
      return trimmed;
    }
    
    if (inMathBlock) {
      return trimmed;
    }
    
    return line;
  });
  
  return processedLines.join('\n');
}

function LinkCard({ href: rawHref, children }) {
  const href = normalizeHref(rawHref);
  // If normalization produced something we can't safely link out to, fall
  // back to plain text so the user never gets accidentally routed in-app.
  if (!href || href === '#') {
    return <span>{children || rawHref}</span>;
  }

  const isCalendar = href.includes('calendar.google.com');
  const isMeet = href.includes('meet.google.com');
  const isZoom = href.includes('zoom.us');
  const isTeams = href.includes('teams.microsoft.com');
  const isEventLink = isCalendar || isMeet || isZoom || isTeams;

  if (!isEventLink) {
    // Prefer the link TEXT the model wrote — [some label](url). Falls back
    // to hostname only when the model emitted a bare URL with no label.
    let displayLabel = '';
    const childText = (() => {
      if (typeof children === 'string') return children;
      if (Array.isArray(children)) return children.filter(c => typeof c === 'string').join('');
      return '';
    })().trim();
    if (childText && childText !== href) {
      displayLabel = childText;
    } else {
      displayLabel = href;
      try {
        const url = new URL(href);
        displayLabel = url.hostname.replace('www.', '');
      } catch {}
    }

    return (
      <a href={href} target="_blank" rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-accent/40 border border-[var(--k-border)] text-[var(--k-brand)] hover:bg-accent hover:border-[var(--k-brand)]/30 transition-all duration-200 no-underline text-xs font-medium my-1"
      >
        <Link className="w-3.5 h-3.5" weight="bold" />
        <span className="truncate max-w-[260px]">{displayLabel}</span>
        <ArrowSquareOut className="w-3 h-3 text-muted-foreground/50" />
      </a>
    );
  }

  const label = isCalendar ? 'View in Google Calendar'
    : isMeet ? 'Join Google Meet'
    : isZoom ? 'Join Zoom Meeting'
    : 'Join Teams Meeting';
  const Icon = isMeet || isZoom || isTeams ? VideoCamera : CalendarCheck;
  const color = isMeet || isZoom || isTeams ? 'text-emerald-400' : 'text-[var(--k-brand)]';
  const bg = isMeet || isZoom || isTeams ? 'bg-emerald-400/10 border-emerald-400/20' : 'bg-[var(--k-brand)]/10 border-[var(--k-brand)]/20';

  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
      className={`my-2 flex items-center gap-3 px-4 py-3 rounded-xl border ${bg} hover:opacity-90 transition-opacity no-underline w-full max-w-sm`}
    >
      <div className={`w-9 h-9 rounded-lg ${bg} flex items-center justify-center shrink-0`}>
        <Icon className={`w-5 h-5 ${color}`} weight="duotone" />
      </div>
      <div className="min-w-0">
        <div className={`text-sm font-semibold ${color}`}>{label}</div>
        <div className="text-[11px] text-muted-foreground truncate">{href.split('?')[0]}</div>
      </div>
      <ArrowSquareOut className="w-4 h-4 text-muted-foreground ml-auto shrink-0" />
    </a>
  );
}

const agentBadge = {
  researcher: { icon: Brain, label: 'Researcher', color: 'text-blue-400', bg: 'bg-blue-400/10' },
  coder: { icon: Code, label: 'Code Interpreter', color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  sales: { icon: ChartBar, label: 'Sales Agent', color: 'text-amber-400', bg: 'bg-amber-400/10' },
};

export function ChatMessage({ message, onOpenArtifact, onRegenerate }) {
  const [copied, setCopied] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const audioRef = useRef(null);

  // Normalize content & attachments (especially for history loaded messages)
  let normalizedContent = message.content || '';
  let attachments = Array.isArray(message.files) ? message.files : [];

  if (Array.isArray(message.content)) {
    const textParts = [];
    const imageParts = [];
    message.content.forEach(part => {
      if (!part) return;
      if (typeof part === 'string') {
        textParts.push(part);
      } else if (part.type === 'text' && part.text) {
        textParts.push(part.text);
      } else if (part.type === 'image_url' && part.image_url?.url) {
        imageParts.push({
          previewUrl: part.image_url.url,
          name: 'Attachment',
          type: 'image/png'
        });
      }
    });
    normalizedContent = textParts.join('\n');
    attachments = [...attachments, ...imageParts];
  } else if (typeof normalizedContent !== 'string') {
    normalizedContent = String(normalizedContent);
  }

  const { sources: extractedSources, cleanText } = extractSources(message.responseText || normalizedContent || '');
  const agent = message.agentType ? agentBadge[message.agentType] : null;
  // Strip any ```question/```ask block — it's rendered as a card docked above
  // the composer (by ChatMain), never inline, so the raw JSON must not leak
  // into the message even when the model emits the fence mid-line.
  const { cleaned: contentSansQuestion } = extractQuestionBlock(cleanText);
  const rawContent = contentSansQuestion
    .replace(/<think>[\s\S]*?<\/think>/g, '')
    .trim();

  const [typedRawContent, setTypedRawContent] = useState(() => {
    return !message.streaming ? rawContent : '';
  });

  const targetContentRef = useRef(rawContent);
  const typedRawContentRef = useRef(typedRawContent);
  const timerRef = useRef(null);

  useEffect(() => {
    targetContentRef.current = rawContent;
    // Immediately bump rendering when new chunk arrives to ensure zero lag
    if (message.streaming) {
      const target = rawContent;
      const current = typedRawContentRef.current;
      if (current.length === 0 && target.length > 0) {
        setTypedRawContent(target.substring(0, Math.min(target.length, 3)));
      }
    }
  }, [rawContent, message.streaming]);

  useEffect(() => {
    typedRawContentRef.current = typedRawContent;
  }, [typedRawContent]);

  // Reset when changing message ID or role
  useEffect(() => {
    if (!message.streaming) {
      setTypedRawContent(rawContent);
    } else {
      setTypedRawContent('');
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, [message.id, message.role]);

  // Immediately catch up when streaming ends
  useEffect(() => {
    if (!message.streaming) {
      setTypedRawContent(rawContent);
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, [message.streaming, rawContent]);

  // Smooth typing effect
  useEffect(() => {
    if (!message.streaming) return;

    if (!timerRef.current) {
      timerRef.current = setInterval(() => {
        const target = targetContentRef.current;
        const current = typedRawContentRef.current;

        if (!target.startsWith(current) || current.length > target.length) {
          setTypedRawContent(target);
        } else if (current.length < target.length) {
          const remaining = target.length - current.length;
          let charsToAppend = 1;
          if (remaining > 50) {
            charsToAppend = Math.ceil(remaining / 5);
          } else if (remaining > 15) {
            charsToAppend = 4;
          } else if (remaining > 5) {
            charsToAppend = 2;
          }
          setTypedRawContent(target.substring(0, current.length + charsToAppend));
        }
      }, 15);
    }
  }, [message.streaming]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  const handleCopy = (text) => {
    const copyText = text || normalizedContent || message.responseText || '';
    if (!copyText) return;
    navigator.clipboard.writeText(copyText).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const stopAudio = () => {
    if (audioRef.current) {
      try {
        // Could be AudioContext (streaming) or Audio element
        if (typeof audioRef.current.close === 'function') audioRef.current.close();
        else { audioRef.current.pause(); audioRef.current.currentTime = 0; }
      } catch {}
      audioRef.current = null;
    }
    setIsPlaying(false);
    setIsSynthesizing(false);
  };

  const handlePlayTTS = async () => {
    if (isPlaying) {
      stopAudio();
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      return;
    }

    // Send the WHOLE cleaned message — the backend Kokoro stream synthesises
    // sentence-by-sentence so long messages still get a fast TTFB. The
    // previous 600-char slice caused everything past the first paragraph to
    // be silently dropped from playback.
    const textToSpeak = stripToolTags(normalizedContent || message.responseText || '')
      .replace(/<think>[\s\S]*?<\/think>/g, '')
      .replace(/<artifact[\s\S]*?<\/artifact>/g, '')
      .replace(/<file[\s\S]*?<\/file>/gi, '')
      .replace(/```[\s\S]*?```/g, '')
      .replace(/!\[[^\]]*\]\([^)]*\)/g, '')       // strip image markdown
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')  // keep link text, drop URL
      .replace(/[#*_~`>]/g, '')
      .replace(/[ \t]+\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();

    if (!textToSpeak) return;

    setIsSynthesizing(true);

    try {
      // Streaming PCM playback — first audio arrives within ~1s instead of waiting for full synthesis
      const SAMPLE_RATE = 24000;
      const response = await ttsAPI.revealIQ.stream(textToSpeak, 'swara-en', 'af_bella', 1.0);
      if (!response.ok) throw new Error(`TTS ${response.status}`);

      const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
      audioRef.current = ctx;
      try { await ctx.resume(); } catch {}

      // ── Jitter buffer ──────────────────────────────────────────────────
      // The server synthesises sentence-by-sentence, so PCM arrives in bursts
      // with gaps between sentences. The old 50ms lead under-ran on those
      // gaps → the audible "break" on desktop. We prime ~300ms before starting,
      // then schedule every arriving frame into the FUTURE (nextTime keeps
      // accumulating), so a synthesis gap is covered by already-scheduled audio
      // instead of becoming silence. A resync guard handles rare true underruns.
      const PRIME_SAMPLES = Math.floor(0.30 * SAMPLE_RATE);
      let nextTime = 0;
      let started = false;
      let pending = [];
      let pendingSamples = 0;
      let leftover = null;

      const scheduleFrame = (float32) => {
        const buf = ctx.createBuffer(1, float32.length, SAMPLE_RATE);
        buf.getChannelData(0).set(float32);
        const src = ctx.createBufferSource();
        src.buffer = buf; src.connect(ctx.destination);
        if (nextTime < ctx.currentTime + 0.02) nextTime = ctx.currentTime + 0.12; // resync
        src.start(nextTime);
        nextTime += buf.duration;
      };
      const startPlayback = () => {
        started = true;
        nextTime = ctx.currentTime + 0.08;
        for (const f of pending) scheduleFrame(f);
        pending = []; pendingSamples = 0;
      };

      const reader = response.body.getReader();
      setIsSynthesizing(false);
      setIsPlaying(true);

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          let combined = value;
          if (leftover) {
            const merged = new Uint8Array(leftover.length + value.length);
            merged.set(leftover); merged.set(value, leftover.length);
            combined = merged; leftover = null;
          }
          let len = combined.length;
          if (len % 2 !== 0) { leftover = combined.slice(len - 1); len -= 1; }
          if (len === 0) continue;
          const int16 = new Int16Array(combined.buffer, combined.byteOffset, len / 2);
          const float32 = new Float32Array(int16.length);
          for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768.0;

          if (started) {
            scheduleFrame(float32);
          } else {
            pending.push(float32); pendingSamples += float32.length;
            if (pendingSamples >= PRIME_SAMPLES) startPlayback();
          }
        }
        // Clip shorter than the prime window — flush what we have.
        if (!started && pending.length) startPlayback();
      } finally {
        reader.cancel().catch(() => {});
        const tail = Math.max(0.3, (nextTime - ctx.currentTime) + 0.3);
        setTimeout(() => { try { ctx.close(); } catch {} audioRef.current = null; setIsPlaying(false); }, tail * 1000);
      }
    } catch (error) {
      console.warn('Streaming TTS failed, falling back to browser speech:', error);
      setIsSynthesizing(false);
      if (window.speechSynthesis) {
        const utter = new SpeechSynthesisUtterance(textToSpeak.slice(0, 400));
        utter.rate = 1.1;
        utter.onend = () => setIsPlaying(false);
        utter.onerror = () => setIsPlaying(false);
        window.speechSynthesis.speak(utter);
        setIsPlaying(true);
      }
    }
  };

  if (message.role === 'user') {
    return (
      <div className="message-user flex justify-end animate-fade-up" data-testid={`message-${message.id}`}>
        <div className="max-w-[85%]">
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-2 justify-end">
              {attachments.map((f, i) => {
                const isImg = f.previewUrl || (f.type && f.type.startsWith('image/'));
                if (isImg && f.previewUrl) {
                  return (
                    <a key={i} href={f.previewUrl} target="_blank" rel="noopener noreferrer"
                       className="block rounded-xl overflow-hidden border border-white/10 max-w-[220px]">
                      <img src={f.previewUrl} alt={f.name}
                           className="w-full h-auto max-h-[200px] object-cover" />
                    </a>
                  );
                }
                return (
                  <div key={i}
                       className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-white/10 border border-white/10 text-[11px] text-white">
                    <Code className="w-3.5 h-3.5" weight="bold" />
                    <span className="max-w-[160px] truncate">{f.name}</span>
                  </div>
                );
              })}
            </div>
          )}
          {normalizedContent && (
            <div className="bg-[var(--k-brand)] text-white px-4 py-3 rounded-2xl rounded-br-md text-sm leading-relaxed shadow-lg shadow-[var(--k-brand)]/10 whitespace-pre-wrap">
              {normalizedContent}
            </div>
          )}
          <div className="text-[10px] text-muted-foreground/50 mt-1 text-right font-medium">{message.timestamp}</div>
        </div>
      </div>
    );
  }



  // Mid-stream code-fence safety: if the response has an odd number of ```
  // fences, the markdown parser will treat everything after the last opener
  // as code — including narrative text the model emits after a code block.
  // Auto-balance by appending a virtual closer. The real closer (when it
  // streams in) just replaces this, so no UX regression.
  const _fenceCount = (typedRawContent.match(/```/g) || []).length;
  let _normalized = _fenceCount % 2 === 1 ? typedRawContent + '\n```' : typedRawContent;
  // Normalize LaTeX delimiters to markdown-math form so remark-math picks
  // them up. Models routinely emit \[ ... \] and \( ... \) instead of
  // $$ ... $$ / $ ... $. Convert only OUTSIDE code blocks.
  _normalized = _normalized.replace(/(```[\s\S]*?```)|\\\[([\s\S]+?)\\\]/g,
    (m, code, math) => code || `$$${math}$$`);
  _normalized = _normalized.replace(/(```[\s\S]*?```)|\\\(([\s\S]+?)\\\)/g,
    (m, code, math) => code || `$${math}$`);

  const displayContent = removeIndentedCodeBlocks(unindentMathBlocks(linkifyContent(splitCrammedEmojis(_normalized))));

  // Merge citations
  const allCitations = [...(message.citations || [])];
  if (extractedSources && Array.isArray(extractedSources)) {
    extractedSources.forEach(s => {
      if (!allCitations.find(c => c.url === s.url)) {
        allCitations.push({
          id: allCitations.length + 1,
          title: s.title || s.site || s.url,
          url: s.url,
          source: s.site || ''
        });
      }
    });
  }

  // Streaming-resume indicator: when the backend still has streaming=true on
  // the message (typical after a screen lock / hard reload mid-generation),
  // show a live "Generating…" pulse so the UI never feels dead.
  const isLiveStreaming = Boolean(message.streaming);
  const hasContent = (rawContent && rawContent.length > 0) ||
                     (message.thinking && message.thinking.length > 0) ||
                     (message.toolResults && message.toolResults.length > 0);

  // "Preparing tool…" pulse: during streaming, if the model has started
  // emitting a tool tag (`[INTEGRATION:` / `[SEARCH:` / `[RUN_PYTHON:` …)
  // but it isn't closed yet, stripToolTags drops the whole open tag — leaving
  // the bubble blank until the closing `]` arrives. For long JSON payloads
  // that's many seconds of dead UI. Show a live placeholder during that gap.
  const _PREAMBLE_TOOL_RE = /\[(INTEGRATION|SEARCH|CALCULATE|RUN_PYTHON|FETCH_URL|CALENDAR_(?:LIST|CREATE|DELETE)|GMAIL_(?:LIST|SEND|READ)|WHATSAPP_SEND|SLACK_POST|HUBSPOT_CREATE_CONTACT|FILE_WRITE|FILE_READ|FILE_LIST|BROWSE_TYPE|BROWSE_CLICK|BROWSE_SCROLL|BROWSE)(?::|\s)/;
  const _toolPrepLabel = (() => {
    if (!isLiveStreaming || !rawContent) return null;
    const m = rawContent.match(_PREAMBLE_TOOL_RE);
    if (!m) return null;
    // If the tag has its closing `]` already, the tool card will render —
    // no need for a placeholder.
    const after = rawContent.slice(m.index);
    if (/\]/.test(after) && after.indexOf(']') < after.length - 1) return null;
    const tag = m[1];
    if (tag === 'INTEGRATION') {
      // Try to extract the tool name (e.g. `mcp_github_search_users`) so the
      // placeholder is specific rather than generic.
      const nameMatch = after.match(/\[INTEGRATION:\s*([a-z0-9_]+)/i);
      const toolName = nameMatch ? nameMatch[1] : 'integration';
      return `Preparing ${toolName.replace(/_/g, ' ')}…`;
    }
    if (tag === 'SEARCH') return 'Searching the web…';
    if (tag === 'CALCULATE') return 'Calculating…';
    if (tag === 'RUN_PYTHON') return 'Running Python…';
    if (tag === 'FETCH_URL') return 'Fetching URL…';
    if (tag === 'FILE_WRITE') {
      const nameMatch = after.match(/\[FILE_WRITE:\s*([^\|\n]+?)\s*\|/);
      return nameMatch ? `Writing ${nameMatch[1].trim()}…` : 'Writing file…';
    }
    if (tag === 'FILE_READ') return 'Reading file…';
    if (tag === 'FILE_LIST') return 'Listing files…';
    if (tag === 'BROWSE') {
      const urlMatch = after.match(/\[BROWSE:\s*(\S+)/);
      return urlMatch ? `Browsing ${urlMatch[1].replace(/^https?:\/\//, '').slice(0, 40)}…` : 'Browsing…';
    }
    if (tag === 'BROWSE_CLICK') return 'Clicking through…';
    if (tag === 'BROWSE_TYPE') {
      const fieldMatch = after.match(/\[BROWSE_TYPE:\s*([^\|\n]+?)\s*\|/);
      return fieldMatch ? `Filling ${fieldMatch[1].trim()}…` : 'Typing…';
    }
    if (tag === 'BROWSE_SCROLL') return 'Scrolling…';
    if (tag.startsWith('CALENDAR_')) return 'Working on calendar…';
    if (tag.startsWith('GMAIL_')) return 'Working on email…';
    if (tag === 'WHATSAPP_SEND') return 'Sending WhatsApp…';
    if (tag === 'SLACK_POST') return 'Posting to Slack…';
    if (tag === 'HUBSPOT_CREATE_CONTACT') return 'Creating HubSpot contact…';
    return 'Preparing tool…';
  })();

  return (
    <div className="message-ai animate-fade-up group" data-testid={`message-${message.id}`}>
      {/* Agent Badge */}
      {agent && (
        <div className="flex items-center gap-2 mb-2">
          <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase ${agent.color} ${agent.bg}`}>
            <agent.icon className="w-3 h-3" weight="duotone" />
            {agent.label}
          </div>
        </div>
      )}

      {/* Live "generating" pulse — visible whenever the backend is still
          streaming this message, so reloads/screen-locks don't show a dead UI */}
      {isLiveStreaming && !hasContent && (
        <div className="py-2">
          <ThinkingTokens />
        </div>
      )}

      {/* Thinking (streaming or collapsed) */}
      {!message.thinkingDone && message.thinking && (
        <div className="mb-3">
          <ThinkingTokens text={message.thinking} />
        </div>
      )}

      {message.thinkingDone && message.thinking && (
        <details className="mb-4 group/details" data-testid="thinking-details">
          <summary className="flex items-center gap-2 cursor-pointer text-[10px] uppercase tracking-widest font-bold text-muted-foreground/60 hover:text-[var(--k-yellow)] transition-colors list-none">
            <Brain className="w-3.5 h-3.5 text-[var(--k-yellow)]" weight="duotone" />
            <span>Process Analysis</span>
            <div className="h-px flex-1 bg-[var(--k-border)] ml-2 opacity-20" />
          </summary>
          <div className="mt-2 pl-4 border-l border-[var(--k-yellow)]/20 py-1">
            <p className="text-[11px] text-muted-foreground/80 font-mono leading-relaxed whitespace-pre-wrap italic">{message.thinking}</p>
          </div>
        </details>
      )}

      {/* ReAct step timeline (shows when agent used tools) */}
      {(message.reactSteps?.length > 0) && (
        <ReActSteps steps={message.reactSteps} isSynthesizing={message.isSynthesizing} />
      )}

      {/* Structured tool output (gmail emails, calendar events, python charts) */}
      {(message.toolResults?.length > 0) && (
        <ToolResultCards results={message.toolResults} />
      )}

      {/* "Preparing tool…" placeholder during the dead window between when
          a tool tag starts streaming and when its closing `]` arrives. Without
          this the bubble looks frozen because stripToolTags drops the open tag. */}
      {_toolPrepLabel && (
        <div className="my-2 flex items-center gap-2 text-xs text-muted-foreground/70 italic">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--k-brand)] opacity-60"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-[var(--k-brand)]"></span>
          </span>
          <span>{_toolPrepLabel}</span>
        </div>
      )}

      {/* Response with markdown */}
      <div className="message-content animate-fade-up w-full max-w-full min-w-0 [overflow-wrap:anywhere]">
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[[rehypeKatex, { strict: false, throwOnError: false, output: 'html' }]]}
          components={{
            a({ href, children }) {
              return <LinkCard href={href}>{children}</LinkCard>;
            },

            // Diagrams (mermaid/svg) must be full-width BLOCKS so the text that
            // follows them stacks underneath, not beside. react-markdown wraps
            // fenced code in <pre>; for diagram languages we unwrap it so the
            // diagram <div> sits directly in the message flow.
            pre({ node, children }) {
              try {
                const codeEl = (node?.children || []).find((c) => c.tagName === 'code');
                const cls = codeEl?.properties?.className || [];
                const langClass = (Array.isArray(cls) ? cls : [cls])
                  .find((c) => typeof c === 'string' && c.startsWith('language-'));
                if (langClass === 'language-mermaid' || langClass === 'language-svg' ||
                    langClass === 'language-question' || langClass === 'language-ask') {
                  return <>{children}</>;
                }
              } catch { /* fall through to default <pre> */ }
              return <pre className="w-full max-w-full min-w-0">{children}</pre>;
            },

            table({ children }) {
              return (
                <div className="overflow-x-auto w-full max-w-full min-w-0 my-6 rounded-xl border border-[var(--k-border)] bg-black/20 shadow-sm">
                  <table className="min-w-full divide-y divide-[var(--k-border)] text-sm">
                    {children}
                  </table>
                </div>
              );
            },
            thead({ children }) {
              return <thead className="bg-white/5">{children}</thead>;
            },
            tbody({ children }) {
              return <tbody className="divide-y divide-[var(--k-border)]">{children}</tbody>;
            },
            tr({ children }) {
              return <tr className="hover:bg-white/[0.02] transition-colors">{children}</tr>;
            },
            th({ children }) {
              return <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wider">{children}</th>;
            },
            td({ children }) {
              return <td className="px-4 py-3 text-foreground whitespace-pre-wrap">{children}</td>;
            },
            code({ node, inline, className, children, ...props }) {
              const match = /language-(\w+)/.exec(className || '');
              const lang = match ? match[1] : '';
              const codeString = String(children).replace(/\n$/, '');

              // Claude-style inline diagrams: a ```mermaid block renders as a
              // live, theme-matched SVG right inside the bubble; a ```svg block
              // renders sanitised in a locked sandbox. Both stay out of the
              // syntax-highlighter path below.
              if (!inline && lang === 'mermaid') {
                return <MermaidDiagram code={codeString} streaming={isLiveStreaming} />;
              }
              // Interactive question blocks are stripped from the message and
              // rendered as a card docked above the composer (see ChatMain), so
              // any that slip through to markdown render nothing inline.
              if (!inline && (lang === 'question' || lang === 'ask')) {
                return null;
              }
              if (!inline && (lang === 'svg' ||
                  (!lang && codeString.includes('\n') && codeString.trim().startsWith('<svg')))) {
                return <SvgBlock code={codeString} streaming={isLiveStreaming} />;
              }

              // Stray-fragment guard: react-markdown promotes single chars to
              // "block" code when the model emits a half-finished fence mid-
              // stream or a 4-space-indented line. Without this, you get a
              // huge CODE · 1 line card wrapping just `/` or `)`. Treat any
              // single-line block code with no language tag and short content
              // as inline — real code blocks always have a language fence or
              // multiple lines.
              const isStray = !inline && !lang && !codeString.includes('\n') && codeString.trim().length < 8;
              if (inline || isStray) {
                return <code className="bg-accent/50 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>{children}</code>;
              }

              if (!className) {
                return (
                  <pre className="my-2 p-3 bg-accent/20 rounded-lg overflow-x-auto text-xs font-mono whitespace-pre-wrap break-words [overflow-wrap:anywhere] leading-relaxed border border-[var(--k-border)]/30 text-foreground/90 w-full max-w-full min-w-0">
                    <code {...props}>{children}</code>
                  </pre>
                );
              }

              const lineCount = codeString.split('\n').length;
              return (
                <div className="relative group/code my-4 rounded-xl overflow-hidden border border-[var(--k-border)] bg-black/40 w-full max-w-full min-w-0">
                  <div className="flex items-center justify-between px-4 py-2 bg-gradient-to-r from-indigo-500/10 via-purple-500/10 to-pink-500/10 border-b border-white/5">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-400/70"></span>
                        <span className="w-2.5 h-2.5 rounded-full bg-yellow-400/70"></span>
                        <span className="w-2.5 h-2.5 rounded-full bg-green-400/70"></span>
                      </span>
                      <span className="text-[10px] font-bold uppercase tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-indigo-300 to-pink-300 truncate">
                        {lang || 'code'}
                      </span>
                      <span className="text-[10px] text-muted-foreground/50 hidden sm:inline">· {lineCount} {lineCount === 1 ? 'line' : 'lines'}</span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => handleCopy(codeString)}
                        className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all"
                        title="Copy Code"
                      >
                        <Copy className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => onOpenArtifact?.({
                          type: 'code',
                          title: `${(lang || 'code').toUpperCase()} Implementation`,
                          code: codeString,
                          language: lang
                        })}
                        className="p-1.5 rounded hover:bg-white/10 text-muted-foreground hover:text-foreground transition-all"
                        title="Open in Canvas"
                      >
                        <ArrowSquareOut className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                  <div className="overflow-x-auto w-full max-w-full">
                    <SyntaxHighlighter
                      language={lang}
                      style={vscDarkPlus}
                      showLineNumbers={lineCount > 4}
                      wrapLongLines={false}
                      customStyle={{
                        margin: 0,
                        padding: '1rem',
                        fontSize: '0.8rem',
                        lineHeight: '1.55',
                        background: 'transparent',
                        maxWidth: '100%',
                      }}
                      lineNumberStyle={{
                        minWidth: '2.25em',
                        paddingRight: '1em',
                        color: 'rgba(148,163,184,0.35)',
                        userSelect: 'none',
                        borderRight: '1px solid rgba(148,163,184,0.08)',
                        marginRight: '0.75em',
                      }}
                      codeTagProps={{
                        style: { fontFamily: 'inherit' }
                      }}
                    >
                      {codeString}
                    </SyntaxHighlighter>
                  </div>
                </div>
              );
            }
          }}
        >
          {displayContent}
        </ReactMarkdown>
      </div>

      {/* Full-capacity → Upgrade-to-PRO card (backend emits event:"capacity",
          upgrade:true for free users when all LLM lanes are saturated). Never
          shown to known-PRO users — belt-and-suspenders in case the backend
          is_pro lookup flaked under load. */}
      {message.upgrade && (typeof localStorage === 'undefined' || localStorage.getItem('k_is_pro') !== '1') && (
        <div className="mt-3 rounded-xl border border-amber-400/30 bg-gradient-to-br from-amber-400/10 to-[var(--k-brand)]/10 p-4">
          <div className="flex items-start gap-3">
            <div className="shrink-0 mt-0.5 w-9 h-9 rounded-lg bg-amber-400/15 flex items-center justify-center">
              <Lightning className="w-5 h-5 text-amber-400" weight="fill" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-foreground">We're at full capacity</div>
              <div className="text-xs text-muted-foreground mt-0.5">
                Free access is throttled right now. <span className="font-medium text-foreground">Kautilya PRO</span> requests
                skip the queue on a reserved lane — no waiting, priority compute.
              </div>
              <a
                href="/dashboard/billing"
                className="inline-flex items-center gap-1.5 mt-3 px-3.5 py-2 rounded-lg bg-gradient-to-r from-amber-400 to-[var(--k-brand)] text-black text-xs font-bold hover:opacity-90 transition-opacity"
              >
                <Crown className="w-4 h-4" weight="fill" />
                Upgrade to PRO
              </a>
            </div>
          </div>
        </div>
      )}

      {/* AI-generated disclosure label (Google Play + IT Rules 2021 compliance) */}
      {!isLiveStreaming && displayContent && (
        <div className="mt-2 flex items-center gap-1.5">
          <span className="text-[9px] font-semibold text-muted-foreground/30 tracking-wider uppercase">AI-generated</span>
          <span className="text-[9px] text-muted-foreground/20">&middot;</span>
          <span className="text-[9px] text-muted-foreground/25">Verify important information independently</span>
        </div>
      )}

      {/* Action Buttons */}
      {!isLiveStreaming && (
        <div className="flex items-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
          <button
            onClick={handlePlayTTS}
            disabled={isSynthesizing}
            className={`p-2 rounded-md transition-all duration-200 ${isPlaying ? 'bg-[var(--k-brand)]/10 text-[var(--k-brand)]' : 'hover:bg-accent text-muted-foreground hover:text-foreground'}`}
            title={isPlaying ? 'Stop voice' : 'Play Kautilya Voice'}
          >
            {isSynthesizing
              ? <SpeakerHigh className="w-4 h-4 animate-pulse" />
              : isPlaying
              ? <StopCircle className="w-4 h-4" weight="bold" />
              : <Play className="w-4 h-4" weight="bold" />}
          </button>

          <button
            onClick={() => handleCopy(rawContent)}
            className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-all duration-200"
            title="Copy Message"
          >
            {copied ? <Check className="w-4 h-4 text-emerald-400" weight="bold" /> : <Copy className="w-4 h-4" weight="bold" />}
          </button>

          <button
            onClick={() => onRegenerate?.(message)}
            className="p-2 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-all duration-200"
            title="Regenerate Response"
          >
            <ArrowsClockwise className="w-4 h-4" weight="bold" />
          </button>
        </div>
      )}

      {/* Truth Lens — cross-model verification badge */}
      {!isLiveStreaming && message.truthLens && (
        <div className="mt-3" data-testid="truth-lens">
          {message.truthLens.verdict === 'verified' ? (
            <span
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-emerald-500/25 bg-emerald-500/10 text-emerald-500 text-[10px] font-bold tracking-wide uppercase"
              title={`A second, independent AI model cross-examined this answer and found no factual errors (confidence ${message.truthLens.confidence}%).`}
            >
              <Check className="w-3 h-3" weight="bold" />
              Cross-model verified
            </span>
          ) : (
            <div className="inline-flex flex-col gap-1 px-3 py-2 rounded-lg border border-amber-500/25 bg-amber-500/10">
              <span className="inline-flex items-center gap-1.5 text-amber-500 text-[10px] font-bold tracking-wide uppercase">
                <Brain className="w-3 h-3" weight="bold" />
                Verify independently
              </span>
              {(message.truthLens.flags || []).length > 0 && (
                <ul className="text-[11px] text-muted-foreground space-y-0.5">
                  {message.truthLens.flags.map((f, i) => (
                    <li key={i}>• {f}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {/* Citations */}
      {allCitations.length > 0 && (
        <div className="mt-6 space-y-2" data-testid="citations-panel">
          <span className="text-[9px] tracking-[0.25em] uppercase font-bold text-muted-foreground/40">Knowledge Sources</span>
          <div className="flex flex-wrap gap-2">
            {allCitations.map((cite) => (
              <a
                key={cite.id}
                href={cite.url}
                target="_blank"
                rel="noopener noreferrer"
                data-testid={`citation-${cite.id}`}
                className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--k-border)] bg-muted/5 hover:bg-accent hover:border-[var(--k-brand)]/20 transition-all duration-200 text-xs group/cite"
              >
                <div className="w-5 h-5 rounded bg-[var(--k-brand)]/10 flex items-center justify-center text-[var(--k-brand)] font-bold text-[10px]">
                  {cite.id}
                </div>
                <span className="text-foreground/90 font-medium truncate max-w-[150px]">{cite.title}</span>
                <ArrowSquareOut className="w-3 h-3 text-muted-foreground/40 group-hover/cite:text-[var(--k-brand)]" />
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Artifact Button */}
      {message.hasArtifact && (
        <button
          data-testid="open-artifact-btn"
          onClick={() => onOpenArtifact?.()}
          className="mt-6 flex items-center gap-3 px-5 py-3 rounded-xl border border-[var(--k-brand)]/20 bg-[var(--k-brand)]/5 hover:bg-[var(--k-brand)]/10 transition-all duration-300 text-sm text-[var(--k-brand)] font-bold group/art shadow-sm"
        >
          <div className="w-8 h-8 rounded-lg bg-[var(--k-brand)]/10 flex items-center justify-center group-hover/art:scale-110 transition-transform">
            <Code className="w-4 h-4" weight="bold" />
          </div>
          <div className="flex flex-col items-start">
            <span className="text-foreground">{message.artifactTitle || 'Interactive Content'}</span>
            <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-bold">Open in Canvas</span>
          </div>
        </button>
      )}

      {!isLiveStreaming && (
        <div className="text-[10px] text-muted-foreground/40 mt-4 flex items-center gap-2">
          <div className="w-1 h-1 rounded-full bg-[var(--k-border)]" />
          {message.timestamp}
        </div>
      )}
    </div>
  );
}
