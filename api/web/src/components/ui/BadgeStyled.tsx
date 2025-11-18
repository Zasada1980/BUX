import * as React from 'react';

export type BadgeStyledVariant = 'default' | 'destructive' | 'outline' | 'secondary';

export interface BadgeStyledProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeStyledVariant;
}

export function BadgeStyled({ variant = 'default', className = '', ...props }: BadgeStyledProps) {
  const baseClasses = 'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors';
  
  const variantClasses: Record<BadgeStyledVariant, string> = {
    default: 'bg-blue-100 text-blue-800',
    destructive: 'bg-red-100 text-red-800',
    outline: 'border border-gray-300 bg-white text-gray-700',
    secondary: 'bg-gray-100 text-gray-800',
  };

  const classes = `${baseClasses} ${variantClasses[variant]} ${className}`;

  return <span className={classes} {...props} />;
}
