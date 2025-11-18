import * as React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

export function Card({ className = '', ...props }: CardProps) {
  return (
    <div
      className={`rounded-lg border bg-card text-card-foreground shadow-sm ${className}`}
      {...props}
    />
  );
}

export interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

export function CardHeader({ className = '', ...props }: CardHeaderProps) {
  return <div className={`flex flex-col space-y-1.5 p-6 ${className}`} {...props} />;
}

export interface CardTitleProps extends React.HTMLAttributes<HTMLHeadingElement> {
  children?: React.ReactNode;
}

export function CardTitle({ className = '', ...props }: CardTitleProps) {
  return (
    <h3
      className={`text-2xl font-semibold leading-none tracking-tight ${className}`}
      {...props}
    />
  );
}

export interface CardDescriptionProps extends React.HTMLAttributes<HTMLParagraphElement> {
  children?: React.ReactNode;
}

export function CardDescription({ className = '', ...props }: CardDescriptionProps) {
  return <p className={`text-sm text-muted-foreground ${className}`} {...props} />;
}

export interface CardContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

export function CardContent({ className = '', ...props }: CardContentProps) {
  return <div className={`p-6 pt-0 ${className}`} {...props} />;
}

export interface CardFooterProps extends React.HTMLAttributes<HTMLDivElement> {
  children?: React.ReactNode;
}

export function CardFooter({ className = '', ...props }: CardFooterProps) {
  return <div className={`flex items-center p-6 pt-0 ${className}`} {...props} />;
}
