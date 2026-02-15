import { actionItemCount, bellPopoverOpen } from "../state.js";

export function NotificationBell() {
  const count = actionItemCount.value;

  const handleClick = () => {
    bellPopoverOpen.value = !bellPopoverOpen.value;
  };

  return (
    <button class="notif-bell" onClick={handleClick} aria-label="Notifications">
      <svg
        width="18"
        height="18"
        viewBox="0 0 16 16"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M4.5 6.5V6a3.5 3.5 0 017 0v.5c0 2 1 3 1 3H3.5s1-1 1-3z"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <path
          d="M6.5 13a1.5 1.5 0 003 0"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      {count > 0 && (
        <span class="notif-badge">{count}</span>
      )}
    </button>
  );
}
