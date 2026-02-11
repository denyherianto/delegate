/**
 * FilterBar — Linear-style composable filter component.
 *
 * Usage:
 *   <FilterBar
 *     filters={[{ field: "status", operator: "is", values: ["in_progress"] }]}
 *     onFiltersChange={(newFilters) => setFilters(newFilters)}
 *     fieldConfig={[
 *       { key: "status", label: "Status", options: ["todo", "in_progress", ...] },
 *       { key: "assignee", label: "Assignee", options: ["alice", "bob"] },
 *     ]}
 *   />
 *
 * Each active filter renders as a pill:  [Status] [is] [In Progress] [x]
 * Clicking any segment opens a dropdown to edit that part.
 * The "+" button starts the add-filter flow: field -> operator -> value.
 */
import { useState, useEffect, useRef, useCallback } from "preact/hooks";
import { cap } from "../utils.js";

// ── Operators ──
const OPERATORS = [
  { key: "is", label: "is" },
  { key: "isNot", label: "is not" },
  { key: "anyOf", label: "any of" },
  { key: "noneOf", label: "none of" },
];

const MULTI_VALUE_OPS = new Set(["anyOf", "noneOf"]);

// ── Dropdown (shared) ──
function Dropdown({ items, onSelect, onClose, multiSelect, selected, anchorRef }) {
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
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); setFocusIdx(i => Math.min(i + 1, filtered.length - 1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setFocusIdx(i => Math.max(i - 1, 0)); }
      if (e.key === "Enter" && filtered.length > 0) { e.preventDefault(); onSelect(filtered[focusIdx]); }
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
          const key = typeof item === "string" ? item : item.key;
          const label = typeof item === "string" ? formatValue(item) : item.label;
          const isSelected = selected && selected.includes(key);
          return (
            <div
              key={key}
              class={
                "fb-dropdown-item" +
                (i === focusIdx ? " focused" : "") +
                (isSelected ? " selected" : "")
              }
              onMouseEnter={() => setFocusIdx(i)}
              onClick={() => onSelect(item)}
            >
              {multiSelect && (
                <span class={"fb-check" + (isSelected ? " checked" : "")}>
                  {isSelected ? "✓" : ""}
                </span>
              )}
              <span>{label}</span>
            </div>
          );
        })}
      </div>
      {multiSelect && selected && selected.length > 0 && (
        <div class="fb-dropdown-done" onClick={onClose}>Done</div>
      )}
    </div>
  );
}

// ── Format helpers ──
function formatValue(v) {
  if (!v) return "(none)";
  return v.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function formatOperator(op) {
  const found = OPERATORS.find(o => o.key === op);
  return found ? found.label : op;
}

// ── Active filter pill ──
function FilterPill({ filter, fieldConfig, onChange, onRemove }) {
  const [editingPart, setEditingPart] = useState(null); // "field" | "op" | "value"
  const pillRef = useRef(null);

  const fieldDef = fieldConfig.find(f => f.key === filter.field);
  const isMulti = MULTI_VALUE_OPS.has(filter.operator);

  const handleFieldSelect = (item) => {
    const key = typeof item === "string" ? item : item.key;
    if (key !== filter.field) {
      onChange({ ...filter, field: key, values: [] });
    }
    setEditingPart(null);
  };

  const handleOpSelect = (item) => {
    const key = typeof item === "string" ? item : item.key;
    const wasMulti = MULTI_VALUE_OPS.has(filter.operator);
    const nowMulti = MULTI_VALUE_OPS.has(key);
    let values = filter.values;
    // If switching single->multi or multi->single, reset values
    if (wasMulti !== nowMulti) values = [];
    onChange({ ...filter, operator: key, values });
    setEditingPart(null);
  };

  const handleValueSelect = (item) => {
    const key = typeof item === "string" ? item : item.key;
    if (isMulti) {
      const current = new Set(filter.values);
      if (current.has(key)) current.delete(key); else current.add(key);
      onChange({ ...filter, values: [...current] });
    } else {
      onChange({ ...filter, values: [key] });
      setEditingPart(null);
    }
  };

  const valuesLabel = filter.values.length === 0
    ? "..."
    : filter.values.map(formatValue).join(", ");

  return (
    <div class="fb-pill" ref={pillRef}>
      <span class="fb-pill-field" onClick={() => setEditingPart(editingPart === "field" ? null : "field")}>
        {fieldDef ? fieldDef.label : filter.field}
      </span>
      <span class="fb-pill-op" onClick={() => setEditingPart(editingPart === "op" ? null : "op")}>
        {formatOperator(filter.operator)}
      </span>
      <span class="fb-pill-value" onClick={() => setEditingPart(editingPart === "value" ? null : "value")}>
        {valuesLabel}
      </span>
      <span class="fb-pill-remove" onClick={onRemove}>&times;</span>

      {editingPart === "field" && (
        <Dropdown
          items={fieldConfig.map(f => ({ key: f.key, label: f.label }))}
          onSelect={handleFieldSelect}
          onClose={() => setEditingPart(null)}
          anchorRef={pillRef}
        />
      )}
      {editingPart === "op" && (
        <Dropdown
          items={OPERATORS}
          onSelect={handleOpSelect}
          onClose={() => setEditingPart(null)}
          anchorRef={pillRef}
        />
      )}
      {editingPart === "value" && fieldDef && (
        <Dropdown
          items={fieldDef.options}
          onSelect={handleValueSelect}
          onClose={() => setEditingPart(null)}
          multiSelect={isMulti}
          selected={filter.values}
          anchorRef={pillRef}
        />
      )}
    </div>
  );
}

// ── Add filter flow ──
function AddFilterButton({ fieldConfig, onAdd }) {
  const [step, setStep] = useState(null); // null | "field" | "op" | "value"
  const [draft, setDraft] = useState({ field: "", operator: "is", values: [] });
  const btnRef = useRef(null);

  const reset = useCallback(() => {
    setStep(null);
    setDraft({ field: "", operator: "is", values: [] });
  }, []);

  const handleFieldSelect = (item) => {
    const key = typeof item === "string" ? item : item.key;
    setDraft(d => ({ ...d, field: key }));
    setStep("op");
  };

  const handleOpSelect = (item) => {
    const key = typeof item === "string" ? item : item.key;
    setDraft(d => ({ ...d, operator: key }));
    setStep("value");
  };

  const handleValueSelect = (item) => {
    const key = typeof item === "string" ? item : item.key;
    const isMulti = MULTI_VALUE_OPS.has(draft.operator);
    if (isMulti) {
      setDraft(d => {
        const current = new Set(d.values);
        if (current.has(key)) current.delete(key); else current.add(key);
        return { ...d, values: [...current] };
      });
    } else {
      onAdd({ ...draft, values: [key] });
      reset();
    }
  };

  const handleValueDone = () => {
    if (draft.values.length > 0) {
      onAdd({ ...draft });
    }
    reset();
  };

  const fieldDef = fieldConfig.find(f => f.key === draft.field);

  return (
    <div class="fb-add-wrap" ref={btnRef}>
      <button class="fb-add-btn" onClick={() => setStep(step ? null : "field")}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
          <line x1="6" y1="2" x2="6" y2="10" /><line x1="2" y1="6" x2="10" y2="6" />
        </svg>
        Filter
      </button>

      {step === "field" && (
        <Dropdown
          items={fieldConfig.map(f => ({ key: f.key, label: f.label }))}
          onSelect={handleFieldSelect}
          onClose={reset}
          anchorRef={btnRef}
        />
      )}
      {step === "op" && (
        <Dropdown
          items={OPERATORS}
          onSelect={handleOpSelect}
          onClose={reset}
          anchorRef={btnRef}
        />
      )}
      {step === "value" && fieldDef && (
        <Dropdown
          items={fieldDef.options}
          onSelect={handleValueSelect}
          onClose={handleValueDone}
          multiSelect={MULTI_VALUE_OPS.has(draft.operator)}
          selected={draft.values}
          anchorRef={btnRef}
        />
      )}
    </div>
  );
}

// ── Main FilterBar ──
export function FilterBar({ filters, onFiltersChange, fieldConfig }) {
  const handleChange = useCallback((idx, updated) => {
    const next = [...filters];
    next[idx] = updated;
    onFiltersChange(next);
  }, [filters, onFiltersChange]);

  const handleRemove = useCallback((idx) => {
    const next = filters.filter((_, i) => i !== idx);
    onFiltersChange(next);
  }, [filters, onFiltersChange]);

  const handleAdd = useCallback((filter) => {
    onFiltersChange([...filters, filter]);
  }, [filters, onFiltersChange]);

  return (
    <div class="fb-bar">
      {filters.map((f, i) => (
        <FilterPill
          key={f.field + "-" + i}
          filter={f}
          fieldConfig={fieldConfig}
          onChange={(updated) => handleChange(i, updated)}
          onRemove={() => handleRemove(i)}
        />
      ))}
      <AddFilterButton fieldConfig={fieldConfig} onAdd={handleAdd} />
      {filters.length > 0 && (
        <button class="fb-clear-btn" onClick={() => onFiltersChange([])}>Clear</button>
      )}
    </div>
  );
}

/**
 * Apply an array of filters to a task list.
 * Reusable logic — call from the parent component.
 */
export function applyFilters(tasks, filters) {
  let list = tasks;
  for (const f of filters) {
    if (!f.values || f.values.length === 0) continue;
    const { field, operator, values } = f;
    const valSet = new Set(values);

    list = list.filter(t => {
      // Get the task's value for this field
      let taskVal = t[field];

      // Handle array fields (repo, tags)
      if (Array.isArray(taskVal)) {
        const taskSet = new Set(taskVal);
        switch (operator) {
          case "is":
          case "anyOf":
            return values.some(v => taskSet.has(v));
          case "isNot":
          case "noneOf":
            return !values.some(v => taskSet.has(v));
          default:
            return true;
        }
      }

      // Handle null/undefined as "(none)"
      const tv = taskVal == null ? "(none)" : String(taskVal);

      switch (operator) {
        case "is":
          return valSet.has(tv);
        case "isNot":
          return !valSet.has(tv);
        case "anyOf":
          return valSet.has(tv);
        case "noneOf":
          return !valSet.has(tv);
        default:
          return true;
      }
    });
  }
  return list;
}
