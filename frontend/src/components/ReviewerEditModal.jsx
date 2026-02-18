import { useState, useEffect, useCallback, useRef } from "preact/hooks";
import { getTaskFile, postReviewerEdits } from "../api.js";

// Language detection from file extension.
// When @codemirror packages are available, map these to CM6 language modules.
const EXT_TO_LANG = {
  py: "python", pyw: "python",
  js: "javascript", jsx: "javascript", mjs: "javascript",
  ts: "typescript", tsx: "typescript",
  css: "css", scss: "css",
  json: "json",
  md: "markdown", markdown: "markdown",
  html: "html", htm: "html",
  sh: "bash", bash: "bash",
  go: "go", rs: "rust", java: "java", rb: "ruby", sql: "sql",
};

function extLang(filepath) {
  const ext = (filepath || "").split(".").pop().toLowerCase();
  return EXT_TO_LANG[ext] || null;
}

// CodeEditor: textarea-based code editor.
// Structured so CodeMirror 6 can replace the internals without changing the
// component interface (content, onChange, lang, disabled props stay the same).
function CodeEditor({ content, onChange, lang, disabled }) {
  const textareaRef = useRef(null);

  // Sync content into textarea when changed externally (tab switch)
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta && ta.value !== content) {
      ta.value = content;
    }
  }, [content]);

  const handleInput = useCallback((e) => {
    onChange(e.target.value);
  }, [onChange]);

  const handleKeyDown = useCallback((e) => {
    // Tab inserts spaces; stop propagation so modal-level handler ignores it
    if (e.key === "Tab") {
      e.preventDefault();
      const ta = e.target;
      const start = ta.selectionStart;
      const end = ta.selectionEnd;
      const newVal = ta.value.substring(0, start) + "    " + ta.value.substring(end);
      ta.value = newVal;
      ta.selectionStart = ta.selectionEnd = start + 4;
      onChange(newVal);
    }
    e.stopPropagation();
  }, [onChange]);

  return (
    <textarea
      ref={textareaRef}
      class="rem-editor-textarea"
      data-lang={lang || ""}
      defaultValue={content}
      onInput={handleInput}
      onKeyDown={handleKeyDown}
      disabled={disabled}
      spellcheck={false}
      autocomplete="off"
      autocorrect="off"
      autocapitalize="off"
    />
  );
}

// OpenFileInput: inline text field for typing a file path.
function OpenFileInput({ onOpen, onCancel }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
  }, []);

  const handleKeyDown = (e) => {
    e.stopPropagation();
    if (e.key === "Escape") { onCancel(); return; }
    if (e.key === "Enter") {
      e.preventDefault();
      if (value.trim()) onOpen(value.trim(), setError);
    }
  };

  return (
    <div class="rem-open-file-row">
      <input
        ref={inputRef}
        type="text"
        class={"rem-open-file-input" + (error ? " rem-open-file-input-error" : "")}
        placeholder="File path (e.g. src/main.py)"
        value={value}
        onInput={(e) => { setValue(e.target.value); setError(null); }}
        onKeyDown={handleKeyDown}
      />
      {error && <span class="rem-open-file-error">{error}</span>}
    </div>
  );
}

// ReviewerEditModal: full-screen editor modal for reviewer inline edits.
//
// Props:
//   taskId       - task ID (number)
//   changedFiles - array of file paths from the diff (pre-fetched by parent)
//   onDone(newSha) - called after edits committed (or if no edits, with currentHeadSha)
//   onDiscard()    - called when reviewer clicks Discard
export function ReviewerEditModal({ taskId, changedFiles, onDone, onDiscard }) {
  // File cache: Map<filepath, { content, headSha, dirty }>
  // content = current editor content for that file
  // headSha = sha at load time (staleness detection)
  // dirty = true if content differs from what was loaded
  const [fileCache, setFileCache] = useState(new Map());
  // Sha from first loaded file -- used as expected_sha for all edits
  const [currentHeadSha, setCurrentHeadSha] = useState(null);
  // Currently displayed file
  const [activeFile, setActiveFile] = useState(null);
  // Whether we are loading a file
  const [fileLoading, setFileLoading] = useState(false);
  // Current editor text (what the textarea shows)
  const [editorContent, setEditorContent] = useState("");
  // Show "Open file..." input inline in tabs row
  const [showOpenFile, setShowOpenFile] = useState(false);
  // Error shown in header
  const [error, setError] = useState(null);
  // Loading state for Done button
  const [doneLoading, setDoneLoading] = useState(false);

  const modalRef = useRef(null);

  // Load a file: fetch from API, update cache, switch editor to it.
  const loadFile = useCallback(async (filepath) => {
    // Already cached -- switch without re-fetching
    const cached = fileCache.get(filepath);
    if (cached) {
      setActiveFile(filepath);
      setEditorContent(cached.content);
      return;
    }

    setFileLoading(true);
    setError(null);
    try {
      const data = await getTaskFile(taskId, filepath);
      if (!data) {
        setError("File not found: " + filepath);
        setFileLoading(false);
        return;
      }
      // Stale check: if a previous file was loaded and the sha differs, bail
      if (currentHeadSha !== null && data.head_sha !== currentHeadSha) {
        setError("Branch changed while editing. Please discard and reload.");
        setFileLoading(false);
        return;
      }
      // First load sets the baseline sha
      if (currentHeadSha === null) {
        setCurrentHeadSha(data.head_sha);
      }
      const entry = { content: data.content, headSha: data.head_sha, dirty: false };
      setFileCache(prev => { const n = new Map(prev); n.set(filepath, entry); return n; });
      setActiveFile(filepath);
      setEditorContent(data.content);
    } catch (e) {
      setError("Failed to load file: " + e.message);
    } finally {
      setFileLoading(false);
    }
  }, [taskId, fileCache, currentHeadSha]);

  // Auto-load first changed file on mount
  useEffect(() => {
    if (changedFiles && changedFiles.length > 0) {
      loadFile(changedFiles[0]);
    }
    // Focus the modal for keyboard shortcuts
    if (modalRef.current) modalRef.current.focus();
  }, []); // eslint-disable-line -- intentionally run once

  // Handle editor text change -- mark file dirty
  const handleEditorChange = useCallback((newContent) => {
    setEditorContent(newContent);
    if (!activeFile) return;
    setFileCache(prev => {
      const entry = prev.get(activeFile);
      if (!entry) return prev;
      const n = new Map(prev);
      n.set(activeFile, { ...entry, content: newContent, dirty: true });
      return n;
    });
  }, [activeFile]);

  // Switch tab: flush current content (preserving dirty flag), then load new file
  const handleTabClick = useCallback((filepath) => {
    if (filepath === activeFile) return;
    // Flush current editor to cache synchronously before switching.
    // Only mark dirty if the editor content actually changed from what was loaded.
    setFileCache(prev => {
      const entry = prev.get(activeFile);
      if (!entry) return prev;
      const n = new Map(prev);
      n.set(activeFile, {
        ...entry,
        content: editorContent,
        dirty: entry.dirty || editorContent !== entry.content,
      });
      return n;
    });
    loadFile(filepath);
  }, [activeFile, editorContent, loadFile]);

  // Open an arbitrary file via the text input
  const handleOpenFile = useCallback(async (filepath, setInputError) => {
    const cached = fileCache.get(filepath);
    if (cached) {
      // Already loaded, just switch to it. Flush current editor first.
      setFileCache(prev => {
        const entry = prev.get(activeFile);
        if (!entry) return prev;
        const n = new Map(prev);
        n.set(activeFile, {
          ...entry,
          content: editorContent,
          dirty: entry.dirty || editorContent !== entry.content,
        });
        return n;
      });
      setActiveFile(filepath);
      setEditorContent(cached.content);
      setShowOpenFile(false);
      return;
    }

    setFileLoading(true);
    try {
      const data = await getTaskFile(taskId, filepath);
      if (!data) {
        if (setInputError) setInputError("File not found");
        setFileLoading(false);
        return;
      }
      if (currentHeadSha !== null && data.head_sha !== currentHeadSha) {
        setError("Branch changed while editing. Please discard and reload.");
        setFileLoading(false);
        setShowOpenFile(false);
        return;
      }
      if (currentHeadSha === null) setCurrentHeadSha(data.head_sha);

      const entry = { content: data.content, headSha: data.head_sha, dirty: false };
      // Flush current editor state before switching, preserving dirty flag correctly.
      setFileCache(prev => {
        const cur = prev.get(activeFile);
        const n = new Map(prev);
        if (cur) {
          n.set(activeFile, {
            ...cur,
            content: editorContent,
            dirty: cur.dirty || editorContent !== cur.content,
          });
        }
        n.set(filepath, entry);
        return n;
      });
      setActiveFile(filepath);
      setEditorContent(data.content);
      setShowOpenFile(false);
    } catch (e) {
      if (setInputError) setInputError("Error: " + e.message);
    } finally {
      setFileLoading(false);
    }
  }, [taskId, fileCache, currentHeadSha, activeFile, editorContent]);

  // Done: collect dirty files -> POST -> call onDone(newSha)
  const handleDone = useCallback(async () => {
    if (doneLoading) return;
    setDoneLoading(true);
    setError(null);

    // Collect dirty files, including current editor state
    const dirtyEdits = [];
    for (const [filepath, entry] of fileCache.entries()) {
      const content = filepath === activeFile ? editorContent : entry.content;
      if (entry.dirty || (filepath === activeFile && content !== entry.content)) {
        dirtyEdits.push({
          file: filepath,
          content,
          expected_sha: currentHeadSha,
        });
      }
    }

    try {
      let newSha = currentHeadSha;
      if (dirtyEdits.length > 0) {
        const result = await postReviewerEdits(taskId, dirtyEdits);
        newSha = result.new_sha;
      }
      onDone(newSha);
    } catch (e) {
      if (e.status === 409) {
        setError("Branch has new commits. Please discard and reload.");
      } else {
        setError("Failed to save: " + e.message);
      }
      setDoneLoading(false);
    }
  }, [doneLoading, fileCache, activeFile, editorContent, currentHeadSha, taskId, onDone]);

  // Discard: no requests, just close
  const handleDiscard = useCallback(() => {
    onDiscard();
  }, [onDiscard]);

  // Keyboard shortcuts: Escape = Discard, Cmd+Enter = Done
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") {
        if (showOpenFile) { setShowOpenFile(false); return; }
        e.stopPropagation(); // prevent panel close
        handleDiscard();
        return;
      }
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleDone();
        return;
      }
    };
    document.addEventListener("keydown", handler, true);
    return () => document.removeEventListener("keydown", handler, true);
  }, [handleDiscard, handleDone, showOpenFile]);

  // Focus trap: keep focus inside modal
  useEffect(() => {
    const modal = modalRef.current;
    if (!modal) return;
    const handleFocusOut = (e) => {
      if (!modal.contains(e.relatedTarget)) {
        const firstFocusable = modal.querySelector("button, textarea, input");
        if (firstFocusable) firstFocusable.focus();
      }
    };
    modal.addEventListener("focusout", handleFocusOut);
    return () => modal.removeEventListener("focusout", handleFocusOut);
  }, []);

  // All visible tabs: changedFiles + any extra opened via "Open file..."
  const extraFiles = [...fileCache.keys()].filter(f => !changedFiles.includes(f));
  const allTabs = [...changedFiles, ...extraFiles];

  const lang = activeFile ? extLang(activeFile) : null;

  return (
    <div class="rem-overlay" ref={modalRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Edit files">
      {/* Header bar */}
      <div class="rem-header">
        <div class="rem-header-left">
          <span class="rem-header-title">Edit &mdash; T{String(taskId).padStart(4, "0")}</span>
        </div>
        <div class="rem-header-right">
          {error && <span class="rem-error-msg">{error}</span>}
          <button
            class="rem-btn-done"
            onClick={handleDone}
            disabled={doneLoading || fileLoading}
          >
            {doneLoading ? "Saving..." : "Done"}
          </button>
          <button
            class="rem-btn-discard"
            onClick={handleDiscard}
            disabled={doneLoading}
          >
            Discard
          </button>
        </div>
      </div>

      {/* File tabs row */}
      <div class="rem-tabs-row">
        {allTabs.map((filepath) => {
          const entry = fileCache.get(filepath);
          const isActive = activeFile === filepath;
          // A tab is dirty if the cache says dirty, or it's the active file and editor differs
          const isDirty = entry
            ? (entry.dirty || (isActive && editorContent !== entry.content))
            : false;
          const label = filepath.split("/").pop();
          return (
            <button
              key={filepath}
              class={"rem-tab" + (isActive ? " active" : "") + (isDirty ? " dirty" : "")}
              onClick={() => handleTabClick(filepath)}
              title={filepath}
            >
              {isDirty ? "\u25cf " : ""}{label}
            </button>
          );
        })}

        {/* Open file input or button */}
        {showOpenFile ? (
          <OpenFileInput
            onOpen={handleOpenFile}
            onCancel={() => setShowOpenFile(false)}
          />
        ) : (
          <button
            class="rem-tab rem-tab-open"
            onClick={() => setShowOpenFile(true)}
          >
            Open file...
          </button>
        )}
      </div>

      {/* Editor */}
      <div class="rem-editor-area">
        {fileLoading ? (
          <div class="rem-placeholder">Loading...</div>
        ) : !activeFile ? (
          <div class="rem-placeholder">
            {changedFiles.length > 0 ? "Select a file above." : "Use \"Open file...\" to open a file."}
          </div>
        ) : (
          <CodeEditor
            key={activeFile}
            content={editorContent}
            onChange={handleEditorChange}
            lang={lang}
            disabled={doneLoading}
          />
        )}
      </div>
    </div>
  );
}
