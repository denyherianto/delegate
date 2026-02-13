import { useState, useEffect, useRef, useCallback } from "preact/hooks";

/**
 * Custom dropdown component replacing native <select>.
 * Inspired by Cursor's mode/agent selector: compact trigger pill,
 * floating menu with styled options and checkmark for selected item.
 *
 * Props:
 *   value      — current selected value
 *   options    — array of { value, label } or strings
 *   onChange   — called with new value
 *   className  — extra class on the trigger
 *   renderLabel — optional fn(option) => string for trigger label
 */
export function CustomSelect({ value, options, onChange, className, renderLabel }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef();

  // Normalise options to { value, label }
  const normalised = options.map(o =>
    typeof o === "string" ? { value: o, label: o } : o
  );

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        setOpen(false);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const selected = normalised.find(o => o.value === value);
  const triggerLabel = selected
    ? (renderLabel ? renderLabel(selected) : selected.label)
    : (value || "Select...");

  const handleSelect = useCallback((v) => {
    onChange(v);
    setOpen(false);
  }, [onChange]);

  return (
    <div class={"csel-wrap" + (className ? " " + className : "")} ref={wrapRef}>
      <button
        class={"csel-trigger" + (open ? " csel-open" : "")}
        type="button"
        onClick={() => setOpen(!open)}
      >
        <span class="csel-label">{triggerLabel}</span>
        <svg class="csel-chevron" width="10" height="6" viewBox="0 0 10 6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M1 1l4 4 4-4" />
        </svg>
      </button>
      {open && (
        <div class="csel-menu">
          {normalised.map(o => (
            <button
              key={o.value}
              class={"csel-option" + (o.value === value ? " csel-selected" : "")}
              type="button"
              onClick={() => handleSelect(o.value)}
            >
              <span class="csel-check">{o.value === value ? "\u2713" : ""}</span>
              <span class="csel-option-label">{o.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
