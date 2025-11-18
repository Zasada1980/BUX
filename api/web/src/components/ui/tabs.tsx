import * as React from 'react';

export interface TabsProps {
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  children: React.ReactNode;
  className?: string;
}

export function Tabs({ defaultValue, value, onValueChange, children, className = '' }: TabsProps) {
  const [selectedTab, setSelectedTab] = React.useState(value || defaultValue || '');
  
  const handleTabChange = (newValue: string) => {
    setSelectedTab(newValue);
    if (onValueChange) {
      onValueChange(newValue);
    }
  };
  
  return (
    <div className={className} data-tab-value={selectedTab}>
      {React.Children.map(children, child => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child, { selectedTab, onTabChange: handleTabChange } as any);
        }
        return child;
      })}
    </div>
  );
}

export interface TabsListProps {
  children: React.ReactNode;
  className?: string;
  selectedTab?: string;
  onTabChange?: (value: string) => void;
}

export function TabsList({ children, className = '', selectedTab, onTabChange }: TabsListProps) {
  return (
    <div className={`inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground ${className}`}>
      {React.Children.map(children, child => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child, { selectedTab, onTabChange } as any);
        }
        return child;
      })}
    </div>
  );
}

export interface TabsTriggerProps {
  value: string;
  children: React.ReactNode;
  className?: string;
  selectedTab?: string;
  onTabChange?: (value: string) => void;
}

export function TabsTrigger({ value, children, className = '', selectedTab, onTabChange }: TabsTriggerProps) {
  const isSelected = selectedTab === value;
  
  return (
    <button
      type="button"
      onClick={() => onTabChange?.(value)}
      className={`inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 ${
        isSelected ? 'bg-background text-foreground shadow-sm' : ''
      } ${className}`}
    >
      {children}
    </button>
  );
}

export interface TabsContentProps {
  value: string;
  children: React.ReactNode;
  className?: string;
  selectedTab?: string;
}

export function TabsContent({ value, children, className = '', selectedTab }: TabsContentProps) {
  if (selectedTab !== value) return null;
  
  return (
    <div className={`mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${className}`}>
      {children}
    </div>
  );
}
