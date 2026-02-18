/**
 * PillSelect — Simple pill-styled single-value dropdown.
 *
 * Matches the FilterBar pill aesthetic but for simple dropdown selection.
 * Used for chat/task filter controls (Team, From, To, Type).
 */
import { useState, useEffect, useRef } from "preact/hooks";
import { cap } from "../utils.js";

// Reuse FilterBar's Dropdown styling approach
function Dropdown({ items, onSelect, onClose, anchorRef }) {
  const ref = useRef(null);
  const [focusIdx, setFocusIdx] = useState(0);
  const [search, setSearch] = useState("");

  // Click-outside close
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target) &&
          (!anchorRef?.current || !anchorRef.current.contains(e.target))) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose, anchorRef]);

  // Keyboard nav
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        e.stopPropagation();
        setFocusIdx(i => Math.min(i + 1, filtered.length - 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        e.stopPropagation();
        setFocusIdx(i => Math.max(i - 1, 0));
      }
      if (e.key === "Enter" && filtered.length > 0) {
        e.preventDefault();
        e.stopPropagation();
        onSelect(filtered[focusIdx]);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [focusIdx, onClose, onSelect, items, search]);

  const filtered = search
    ? items.filter(it => {
        const label = typeof it === "string" ? it : it.label;
        return label.toLowerCase().includes(search.toLowerCase());
      })
    : items;

  // Reset focus on search change
  useEffect(() => setFocusIdx(0), [search]);

  const showSearch = items.length > 5;

  return (
    <div class="fb-dropdown" ref={ref}>
      {showSearch && (
        <input
          class="fb-dropdown-search"
          type="text"
          placeholder="Search..."
          value={search}
          onInput={(e) => setSearch(e.target.value)}
          autoFocus
        />
      )}
      <div class="fb-dropdown-list">
        {filtered.length === 0 && <div class="fb-dropdown-empty">No matches</div>}
        {filtered.map((item, i) => {
          const key = typeof item === "string" ? item : item.value;
          const label = typeof item === "string" ? item : item.label;
          return (
            <div
              key={key}
              class={"fb-dropdown-item" + (i === focusIdx ? " focused" : "")}
              onMouseEnter={() => setFocusIdx(i)}
              onClick={() => onSelect(item)}
            >
              <span>{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * PillSelect component
 *
 * @param {string} label - Left segment label (e.g., "From", "Team", "Type")
 * @param {string} value - Current selected value
 * @param {Array} options - Array of { value, label } objects or strings
 * @param {Function} onChange - Callback with selected value
 * @param {string} className - Optional additional class
 */
export function PillSelect({ label, value, options, onChange, className }) {
  const [isOpen, setIsOpen] = useState(false);
  const pillRef = useRef(null);

  const handleSelect = (item) => {
    const selectedValue = typeof item === "string" ? item : item.value;
    onChange(selectedValue);
    setIsOpen(false);
  };

  // Find display label for current value
  const displayValue = (() => {
    if (!value) return "All";
    const option = options.find(opt => {
      const optVal = typeof opt === "string" ? opt : opt.value;
      return optVal === value;
    });
    if (!option) return cap(value);
    return typeof option === "string" ? option : option.label;
  })();

  return (
    <div class={"pill-select" + (className ? " " + className : "")} ref={pillRef}>
      <span class="pill-select-label">{label}</span>
      <span
        class="pill-select-value"
        onClick={() => setIsOpen(!isOpen)}
        title={`Change ${label}`}
      >
        {displayValue}
        <svg class="pill-select-chevron" width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="1,3 4,6 7,3" />
        </svg>
      </span>
      {isOpen && (
        <Dropdown
          items={options}
          onSelect={handleSelect}
          onClose={() => setIsOpen(false)}
          anchorRef={pillRef}
        />
      )}
    </div>
  );
}
