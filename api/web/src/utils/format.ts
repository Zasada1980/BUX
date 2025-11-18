// Utility functions for data formatting
// Used across pages for consistent display formatting

/**
 * Format money amount with currency symbol
 * @param amount - Decimal amount or number
 * @param currency - Currency code (default: 'ILS')
 * @returns Formatted string like "₪1,234.56"
 */
export function formatMoney(amount: number | string | null | undefined, currency: string = 'ILS'): string {
  if (amount === null || amount === undefined) return '—';
  
  const numAmount = typeof amount === 'string' ? parseFloat(amount) : amount;
  if (isNaN(numAmount)) return '—';
  
  const formatted = new Intl.NumberFormat('he-IL', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numAmount);
  
  return formatted;
}

/**
 * Format date to localized string
 * @param date - Date string or Date object
 * @param includeTime - Include time in output (default: false)
 * @returns Formatted date like "15.11.2025" or "15.11.2025, 14:30"
 */
export function formatDate(date: string | Date | null | undefined, includeTime: boolean = false): string {
  if (!date) return '—';
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  if (isNaN(dateObj.getTime())) return '—';
  
  const options: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  };
  
  if (includeTime) {
    options.hour = '2-digit';
    options.minute = '2-digit';
  }
  
  return dateObj.toLocaleString('ru-RU', options);
}

/**
 * Format duration in seconds to "Xh Ym" format
 * @param seconds - Duration in seconds
 * @returns Formatted string like "8h 30m" or "45m"
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || seconds === 0) return '0m';
  
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  
  if (hours > 0) {
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
  }
  
  return `${minutes}m`;
}

/**
 * Truncate long text with ellipsis
 * @param text - Text to truncate
 * @param maxLength - Maximum length (default: 60)
 * @returns Truncated text
 */
export function truncate(text: string | null | undefined, maxLength: number = 60): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength - 3) + '...';
}
