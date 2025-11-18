import './Pagination.css';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  itemsPerPage?: number;
  totalItems?: number;
}

export default function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  itemsPerPage,
  totalItems,
}: PaginationProps) {
  const canGoPrevious = currentPage > 1;
  const canGoNext = currentPage < totalPages;

  // Generate page numbers to display
  const getPageNumbers = () => {
    const pages: (number | string)[] = [];
    const showPages = 5; // Show max 5 page buttons

    if (totalPages <= showPages) {
      // Show all pages
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      // Always show first page
      pages.push(1);

      if (currentPage > 3) {
        pages.push('...');
      }

      // Show current page and neighbors
      for (
        let i = Math.max(2, currentPage - 1);
        i <= Math.min(totalPages - 1, currentPage + 1);
        i++
      ) {
        pages.push(i);
      }

      if (currentPage < totalPages - 2) {
        pages.push('...');
      }

      // Always show last page
      if (totalPages > 1) {
        pages.push(totalPages);
      }
    }

    return pages;
  };

  if (totalPages <= 1) {
    return null;
  }

  return (
    <div className="pagination">
      <div className="pagination-info">
        {totalItems !== undefined && itemsPerPage !== undefined && (
          <span className="pagination-text">
            Showing {Math.min((currentPage - 1) * itemsPerPage + 1, totalItems)} -{' '}
            {Math.min(currentPage * itemsPerPage, totalItems)} of {totalItems} items
          </span>
        )}
      </div>

      <div className="pagination-controls">
        <button
          className="pagination-button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={!canGoPrevious}
          aria-label="Previous page"
        >
          ‹ Previous
        </button>

        <div className="pagination-pages">
          {getPageNumbers().map((page, index) => {
            if (page === '...') {
              return (
                <span key={`ellipsis-${index}`} className="pagination-ellipsis">
                  ...
                </span>
              );
            }

            return (
              <button
                key={page}
                className={`pagination-page ${page === currentPage ? 'active' : ''}`}
                onClick={() => onPageChange(page as number)}
              >
                {page}
              </button>
            );
          })}
        </div>

        <button
          className="pagination-button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={!canGoNext}
          aria-label="Next page"
        >
          Next ›
        </button>
      </div>
    </div>
  );
}
