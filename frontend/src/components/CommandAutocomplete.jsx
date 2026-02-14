/**
 * Autocomplete dropdown for slash commands — pure rendering component.
 *
 * Anchored above the chat-input-box via CSS (position: absolute; bottom: 100%).
 * Keyboard navigation is handled by the parent via the onKeyDown callback.
 *
 * @param {Object}   props
 * @param {Array}    props.commands      - Filtered command objects to display
 * @param {number}   props.selectedIndex - Currently highlighted index
 * @param {Function} props.onSelect      - Called with the chosen command object
 */
export function CommandAutocomplete({ commands, selectedIndex, onSelect }) {
  if (!commands || !commands.length) return null;

  return (
    <div class="command-autocomplete">
      {commands.map((cmd, idx) => (
        <div
          key={cmd.name}
          class={`command-autocomplete-item ${idx === selectedIndex ? "selected" : ""}`}
          onMouseDown={(e) => { e.preventDefault(); onSelect(cmd); }}
        >
          <span class="command-name">/{cmd.name}</span>
          <span class="command-description">{cmd.description}</span>
        </div>
      ))}
    </div>
  );
}
