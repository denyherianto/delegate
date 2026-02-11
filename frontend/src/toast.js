import { signal } from "@preact/signals";

export const toasts = signal([]);

const MAX_TOASTS = 3;

export function showToast(message, type = "error") {
  const id = Date.now();

  // Add new toast
  const newToasts = [...toasts.value, { id, message, type }];

  // If exceeding max, remove oldest
  if (newToasts.length > MAX_TOASTS) {
    toasts.value = newToasts.slice(-MAX_TOASTS);
  } else {
    toasts.value = newToasts;
  }

  // Auto-dismiss after 5 seconds
  setTimeout(() => dismissToast(id), 5000);
}

export function dismissToast(id) {
  toasts.value = toasts.value.filter(t => t.id !== id);
}
