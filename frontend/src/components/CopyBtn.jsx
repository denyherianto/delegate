import { useState, useCallback } from "preact/hooks";

/**
 * Tiny inline copy button. Shows a clipboard icon; on click copies `text`
 * and briefly swaps to a checkmark.
 *
 * Usage: <CopyBtn text="T0003" />
 */
export function CopyBtn({ text }) {
  const [copied, setCopied] = useState(false);

  const handleClick = useCallback((e) => {
    e.stopPropagation();
    e.preventDefault();
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch(() => {});
  }, [text]);

  return (
    <span
      class={"copy-btn" + (copied ? " copied" : "")}
      title={copied ? "Copied!" : "Copy"}
      onClick={handleClick}
    >
      {copied ? (
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="3 8 7 12 13 4" />
        </svg>
      ) : (
        <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="5" y="5" width="9" height="9" rx="1.5" />
          <path d="M5 11H3.5A1.5 1.5 0 0 1 2 9.5v-7A1.5 1.5 0 0 1 3.5 1h7A1.5 1.5 0 0 1 12 2.5V5" />
        </svg>
      )}
    </span>
  );
}
