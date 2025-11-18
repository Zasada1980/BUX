import './DataTable.css';

interface Column<T> {
  key: keyof T | string;
  label: string | React.ReactNode;
  render?: (item: T) => React.ReactNode;
  sortable?: boolean;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string | number;
  onSort?: (key: string, direction: 'asc' | 'desc') => void;
  sortKey?: string;
  sortDirection?: 'asc' | 'desc';
  emptyMessage?: string;
}

export function DataTable<T extends Record<string, any>>({
  columns,
  data,
  keyExtractor,
  onSort,
  sortKey,
  sortDirection = 'asc',
  emptyMessage = 'No data available',
}: DataTableProps<T>) {
  const handleSort = (key: string) => {
    if (!onSort) return;
    const newDirection = sortKey === key && sortDirection === 'asc' ? 'desc' : 'asc';
    onSort(key, newDirection);
  };

  if (data.length === 0) {
    return (
      <div className="data-table-empty">
        <p>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className="data-table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((column) => {
              const key = String(column.key);
              const isSortable = column.sortable !== false;
              const isActiveSortKey = sortKey === key;

              return (
                <th
                  key={key}
                  className={isSortable ? 'sortable' : ''}
                  onClick={() => isSortable && handleSort(key)}
                >
                  <div className="th-content">
                    <span>{column.label}</span>
                    {isSortable && isActiveSortKey && (
                      <span className="sort-indicator">
                        {sortDirection === 'asc' ? '↑' : '↓'}
                      </span>
                    )}
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr key={keyExtractor(item)}>
              {columns.map((column) => {
                const key = String(column.key);
                const content = column.render
                  ? column.render(item)
                  : item[column.key as keyof T];

                return <td key={key}>{content}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
