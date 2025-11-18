import * as React from 'react';

interface AlertDialogProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: React.ReactNode;
}

interface AlertDialogContentProps {
  children: React.ReactNode;
  className?: string;
}

interface AlertDialogHeaderProps {
  children: React.ReactNode;
}

interface AlertDialogFooterProps {
  children: React.ReactNode;
}

interface AlertDialogTitleProps {
  children: React.ReactNode;
}

interface AlertDialogDescriptionProps {
  children: React.ReactNode;
}

interface AlertDialogActionProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

interface AlertDialogCancelProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

export function AlertDialog({ open, onOpenChange, children }: AlertDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="fixed inset-0 bg-black/50"
        onClick={() => onOpenChange?.(false)}
      />
      {children}
    </div>
  );
}

export function AlertDialogContent({ children, className = '' }: AlertDialogContentProps) {
  return (
    <div
      className={`relative z-50 bg-white rounded-lg shadow-lg max-w-md w-full mx-4 p-6 ${className}`}
      role="alertdialog"
      aria-modal="true"
    >
      {children}
    </div>
  );
}

export function AlertDialogHeader({ children }: AlertDialogHeaderProps) {
  return <div className="space-y-2 mb-4">{children}</div>;
}

export function AlertDialogFooter({ children }: AlertDialogFooterProps) {
  return (
    <div className="flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-6">
      {children}
    </div>
  );
}

export function AlertDialogTitle({ children }: AlertDialogTitleProps) {
  return (
    <h2 className="text-lg font-semibold text-gray-900">
      {children}
    </h2>
  );
}

export function AlertDialogDescription({ children }: AlertDialogDescriptionProps) {
  return (
    <p className="text-sm text-gray-600">
      {children}
    </p>
  );
}

export function AlertDialogAction({ children, className = '', ...props }: AlertDialogActionProps) {
  return (
    <button
      className={`inline-flex items-center justify-center px-4 py-2 text-sm font-medium rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function AlertDialogCancel({ children, className = '', ...props }: AlertDialogCancelProps) {
  return (
    <button
      className={`inline-flex items-center justify-center px-4 py-2 text-sm font-medium border border-gray-300 rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
