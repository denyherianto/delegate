import { useState, useEffect, useCallback } from "preact/hooks";

const UPGRADE_COMMANDS = "pip install --upgrade delegate-ai\ndelegate stop\ndelegate start";

export function UpdateModal({ versionInfo, onClose }) {
  const [copied, setCopied] = useState(false);

  // Close on Escape key
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(UPGRADE_COMMANDS).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, []);

  const handleBackdropClick = useCallback((e) => {
    if (e.target === e.currentTarget) onClose();
  }, [onClose]);

  return (
    <div class="modal-overlay" onClick={handleBackdropClick} style={{ zIndex: 9999 }}>
      <div class="modal-box update-modal">
        <div class="modal-header">
          <span class="modal-title">Update available</span>
        </div>
        <div class="modal-body">
          <p class="update-modal-desc">
            Delegate v{versionInfo.latest} is available. You have v{versionInfo.current}.
          </p>
          <div class="update-modal-code">
            <pre>{UPGRADE_COMMANDS}</pre>
          </div>
          <div class="update-modal-actions">
            <button class="update-modal-copy-btn" onClick={handleCopy}>
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>
        </div>
        <div class="modal-footer">
          <button class="modal-btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
