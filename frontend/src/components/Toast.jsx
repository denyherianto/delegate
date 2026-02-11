import { toasts, dismissToast } from "../toast.js";

function Toast({ toast }) {
  const { id, message, type } = toast;

  const handleDismiss = () => {
    dismissToast(id);
  };

  return (
    <div class={`toast toast-${type}`}>
      <div class="toast-message">{message}</div>
      <button class="toast-close" onClick={handleDismiss} aria-label="Close">
        ×
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toastList = toasts.value;

  if (toastList.length === 0) return null;

  return (
    <div class="toast-container">
      {toastList.map(toast => (
        <Toast key={toast.id} toast={toast} />
      ))}
    </div>
  );
}
