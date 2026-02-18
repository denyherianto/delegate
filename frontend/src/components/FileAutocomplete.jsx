import { useState, useEffect, useRef, useCallback } from "preact/hooks";

/**
 * FileAutocomplete — reusable input-with-dropdown for path completion.
 *
 * Props:
 *   value            string         — current input value
 *   onChange         (val) => void  — called on every keystroke
 *   onSelect         (path) => void — called when user confirms a path (Enter or click)
 *   onCancel         () => void     — called on Escape
 *   fetchSuggestions async (query: string) => string[] — injected by parent
 *   placeholder      string, optional
 *   className        string, optional — extra class on the wrapper div
 *   autoFocus        bool, optional  — default true
 *
 * Keyboard:
 *   ArrowDown/ArrowUp — move selection in dropdown
 *   Tab               — complete to selected item (fills input, does NOT submit)
 *   Enter             — onSelect(selected item) or onSelect(value) if nothing selected
 *   Escape            — onCancel()
 *
 * Click on suggestion — onSelect(path)
 * Directories are shown with trailing '/'. Selecting a dir fills the input
 * but does NOT call onSelect — the parent decides what to do with dirs.
 */
export function FileAutocomplete({
  value,
  onChange,
  onSelect,
  onCancel,
  fetchSuggestions,
  placeholder = "",
  className = "",
  autoFocus = true,
}) {
  const [suggestions, setSuggestions] = useState([]);   // string[]
  const [selectedIdx, setSelectedIdx] = useState(-1);   // -1 = nothing selected
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [above, setAbove] = useState(false);             // true when dropdown renders above input

  const inputRef = useRef(null);
  const wrapRef = useRef(null);
  const debounceRef = useRef(null);
  const latestQueryRef = useRef("");  // guard stale async results

  // Auto-focus on mount
  useEffect(() => {
    if (autoFocus && inputRef.current) inputRef.current.focus();
  }, [autoFocus]);

  // Fetch suggestions whenever value changes (debounced 150ms)
  useEffect(() => {
    clearTimeout(debounceRef.current);
    const query = value;
    latestQueryRef.current = query;

    debounceRef.current = setTimeout(async () => {
      try {
        const results = await fetchSuggestions(query);
        // Discard if a newer query started while we were waiting
        if (latestQueryRef.current !== query) return;
        setSuggestions(results || []);
        setSelectedIdx(-1);
        setDropdownOpen((results || []).length > 0);
      } catch (_) {
        // Silently ignore fetch errors — just hide the dropdown
        setSuggestions([]);
        setDropdownOpen(false);
      }
    }, 150);

    return () => clearTimeout(debounceRef.current);
  }, [value, fetchSuggestions]);

  // Position: flip above input when near bottom of viewport
  useEffect(() => {
    if (!dropdownOpen || !wrapRef.current) return;
    const rect = wrapRef.current.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    setAbove(spaceBelow < 260); // 240px max-height + 20px margin
  }, [dropdownOpen, suggestions]);

  const selectByIndex = useCallback((idx) => {
    const path = suggestions[idx];
    if (!path) return;
    if (path.endsWith("/")) {
      // Directory — fill input, keep dropdown open for further typing
      onChange(path);
      // Reset so next render refetches with the new dir prefix
      setDropdownOpen(false);
    } else {
      // File — close and call onSelect
      setDropdownOpen(false);
      setSuggestions([]);
      onSelect(path);
    }
  }, [suggestions, onChange, onSelect]);

  const handleKeyDown = useCallback((e) => {
    // Escape: close dropdown first; if already closed, propagate to parent onCancel
    if (e.key === "Escape") {
      if (dropdownOpen) {
        e.stopPropagation();
        setDropdownOpen(false);
        setSelectedIdx(-1);
        return;
      }
      // Dropdown already closed — let parent handle Escape
      onCancel();
      return;
    }

    if (!dropdownOpen || suggestions.length === 0) {
      if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        onSelect(value);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIdx(i => (i + 1) % suggestions.length);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIdx(i => (i <= 0 ? suggestions.length - 1 : i - 1));
      return;
    }
    if (e.key === "Tab") {
      e.preventDefault();
      if (selectedIdx >= 0) {
        // Complete to selected — fill input, don't submit
        const path = suggestions[selectedIdx];
        onChange(path);
        setDropdownOpen(false);
        setSelectedIdx(-1);
      }
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      if (selectedIdx >= 0) {
        selectByIndex(selectedIdx);
      } else {
        // No selection — submit raw value
        setDropdownOpen(false);
        onSelect(value);
      }
    }
  }, [dropdownOpen, suggestions, selectedIdx, value, onChange, onSelect, onCancel, selectByIndex]);

  const handleInput = useCallback((e) => {
    onChange(e.target.value);
    setSelectedIdx(-1);
  }, [onChange]);

  const handleItemMouseDown = useCallback((e, idx) => {
    // mousedown fires before blur — prevent blur from stealing focus
    e.preventDefault();
    selectByIndex(idx);
  }, [selectByIndex]);

  const handleBlur = useCallback(() => {
    // Close dropdown when focus leaves the component entirely
    // Small delay so mousedown on a suggestion fires first
    setTimeout(() => {
      if (document.activeElement !== inputRef.current) {
        setDropdownOpen(false);
        setSelectedIdx(-1);
      }
    }, 150);
  }, []);

  const dropdownClass = [
    "file-ac-dropdown",
    above ? "file-ac-dropdown-above" : "",
  ].filter(Boolean).join(" ");

  return (
    <div class={["file-ac-wrap", className].filter(Boolean).join(" ")} ref={wrapRef}>
      <input
        ref={inputRef}
        type="text"
        class="file-ac-input"
        value={value}
        placeholder={placeholder}
        onInput={handleInput}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        autoComplete="off"
        spellCheck={false}
      />
      {dropdownOpen && suggestions.length > 0 && (
        <div class={dropdownClass} role="listbox">
          {suggestions.slice(0, 20).map((path, idx) => {
            const isDir = path.endsWith("/");
            const itemClass = [
              "file-ac-item",
              isDir ? "is-dir" : "",
              idx === selectedIdx ? "selected" : "",
            ].filter(Boolean).join(" ");
            return (
              <div
                key={path}
                class={itemClass}
                role="option"
                aria-selected={idx === selectedIdx}
                onMouseDown={(e) => handleItemMouseDown(e, idx)}
                onMouseEnter={() => setSelectedIdx(idx)}
              >
                {path}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
