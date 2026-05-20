const text = `🔥 TOP 3 UNITS TO START WITH
(Agar sirf 3 units hi padh sakte ho, toh inhein choose karo)

1️⃣ UNIT 3: DC GENERATORS (15-20 Marks)
Why? → Most important unit, numericals bohot aate hain. Key Topics: ✅ Construction (Yoke, Poles) ✅ EMF Equation ✅ Types

\`\`\`
✅ Do not split inside code block ✅
\`\`\`

📌 Most Repeated Numerical:
Find EMF generated`;

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

console.log("Input:\n", text);
console.log("\n========================\nOutput:\n" + splitCrammedEmojis(text));
