import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  type Row,
  useReactTable,
} from "@tanstack/react-table";
import type { ReactNode } from "react";

import { EmptyState, ErrorState } from "@/components/states";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[] | undefined;
  isLoading: boolean;
  error?: unknown;
  onRetry?: () => void;
  /** Phones get cards instead of a table. */
  renderCard: (row: Row<T>) => ReactNode;
  empty: { title: string; message?: ReactNode; action?: ReactNode };
  getRowId?: (row: T) => string;
  caption: string;
}

/** Table on tablet/desktop, stacked cards on phones. */
export function DataTable<T>({
  columns,
  data,
  isLoading,
  error,
  onRetry,
  renderCard,
  empty,
  getRowId,
  caption,
}: DataTableProps<T>) {
  const table = useReactTable({
    data: data ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    ...(getRowId ? { getRowId } : {}),
  });

  if (error) {
    return <ErrorState message="We couldn't load this list." {...(onRetry ? { onRetry } : {})} />;
  }
  if (isLoading) {
    return (
      <div className="flex flex-col gap-3 p-4" role="status" aria-live="polite">
        <span className="sr-only">Loading</span>
        {Array.from({ length: 5 }, (_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }
  const rows = table.getRowModel().rows;
  if (rows.length === 0) {
    return <EmptyState title={empty.title} message={empty.message} action={empty.action} />;
  }
  return (
    <>
      <div className="hidden md:block">
        <Table>
          <caption className="sr-only">{caption}</caption>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id} className="hover:bg-transparent">
                {hg.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className="text-muted-foreground h-11 px-4 text-xs font-semibold tracking-wide uppercase"
                  >
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id} className="h-14">
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id} className="px-4">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <ul className="divide-y md:hidden" aria-label={caption}>
        {rows.map((row) => (
          <li key={row.id} className="p-4">
            {renderCard(row)}
          </li>
        ))}
      </ul>
    </>
  );
}
