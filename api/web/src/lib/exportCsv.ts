/**
 * CSV Export Utility
 * 
 * Provides generic CSV export functionality with UTF-8 BOM for Excel compatibility.
 */

export interface CsvColumn<T = any> {
  key: string;
  label: string;
  format?: (value: any, row: T) => string;
}

/**
 * Export data to CSV file
 * 
 * @param rows - Array of data objects to export
 * @param columns - Column definitions (key, label, optional format function)
 * @param filename - Output filename (without .csv extension)
 * 
 * @example
 * exportToCsv(
 *   users,
 *   [
 *     { key: 'id', label: 'ID' },
 *     { key: 'name', label: 'Name' },
 *     { key: 'amount', label: 'Amount', format: (val) => `₪${val}` }
 *   ],
 *   'users_2025-11-15'
 * );
 */
export function exportToCsv<T = any>(
  rows: T[],
  columns: CsvColumn<T>[],
  filename: string
): void {
  if (!rows || rows.length === 0) {
    throw new Error('No data to export');
  }

  // Build CSV header
  const headers = columns.map(col => escapeCsvValue(col.label));
  const headerLine = headers.join(',');

  // Build CSV rows
  const dataLines = rows.map(row => {
    const values = columns.map(col => {
      const value = getNestedValue(row, col.key);
      const formatted = col.format ? col.format(value, row) : value;
      return escapeCsvValue(formatted);
    });
    return values.join(',');
  });

  // Combine header and data
  const csvContent = [headerLine, ...dataLines].join('\n');

  // Add UTF-8 BOM for Excel compatibility
  const bom = '\uFEFF';
  const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=utf-8;' });

  // Trigger download
  triggerDownload(blob, `${filename}.csv`);
}

/**
 * Get nested object value by dot-notation key (e.g., "user.name")
 */
function getNestedValue(obj: any, key: string): any {
  if (!key.includes('.')) {
    return obj[key];
  }
  
  return key.split('.').reduce((current, part) => {
    return current?.[part];
  }, obj);
}

/**
 * Escape CSV value (handle quotes, commas, newlines)
 */
function escapeCsvValue(value: any): string {
  if (value === null || value === undefined) {
    return '';
  }

  const stringValue = String(value);

  // If contains comma, quote, or newline → wrap in quotes and escape existing quotes
  if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
    return `"${stringValue.replace(/"/g, '""')}"`;
  }

  return stringValue;
}

/**
 * Trigger browser download for a blob
 */
function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.style.display = 'none';
  
  document.body.appendChild(link);
  link.click();
  
  // Cleanup
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Get current date in YYYY-MM-DD format for filenames
 */
export function getCurrentDateForFilename(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}
