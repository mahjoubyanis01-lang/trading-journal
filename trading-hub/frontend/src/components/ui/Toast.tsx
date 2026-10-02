import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';
import { CheckCircle2, Info, XCircle } from 'lucide-react';
import { cn } from '../../lib/cn';

type ToastKind = 'success' | 'error' | 'info';
interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

const ToastCtx = createContext<(kind: ToastKind, message: string) => void>(() => {});

export function useToast() {
  return useContext(ToastCtx);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const push = useCallback((kind: ToastKind, message: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, kind, message }]);
    window.setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id));
    }, 4000);
  }, []);

  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              'pointer-events-auto flex items-start gap-2 rounded-lg border bg-panel px-3 py-2.5 text-sm shadow-xl',
              t.kind === 'success' && 'border-op/40 text-zinc-200',
              t.kind === 'error' && 'border-err/40 text-zinc-200',
              t.kind === 'info' && 'border-info/40 text-zinc-200',
            )}
          >
            {t.kind === 'success' && <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-op" />}
            {t.kind === 'error' && <XCircle size={16} className="mt-0.5 shrink-0 text-err" />}
            {t.kind === 'info' && <Info size={16} className="mt-0.5 shrink-0 text-info" />}
            <span className="leading-snug">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
