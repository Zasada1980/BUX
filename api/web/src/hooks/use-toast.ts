// Toast hook compatible with shadcn/ui pattern

export interface Toast {
  id: string;
  title?: string;
  description?: string;
  variant?: 'default' | 'destructive';
}

interface ToastState {
  toasts: Toast[];
}

const toastState: ToastState = {
  toasts: [],
};

let listeners: Array<(state: ToastState) => void> = [];

function notify() {
  listeners.forEach(listener => listener(toastState));
}

export function toast({ title, description, variant = 'default' }: Omit<Toast, 'id'>) {
  const id = Math.random().toString(36).substring(7);
  const newToast: Toast = { id, title, description, variant };
  
  toastState.toasts = [...toastState.toasts, newToast];
  notify();
  
  // Auto-dismiss after 5 seconds
  setTimeout(() => {
    toastState.toasts = toastState.toasts.filter(t => t.id !== id);
    notify();
  }, 5000);
}

export function useToast() {
  return {
    toast,
    toasts: toastState.toasts,
    dismiss: (id: string) => {
      toastState.toasts = toastState.toasts.filter(t => t.id !== id);
      notify();
    },
  };
}
