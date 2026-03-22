import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table'
import type { ResourceAccessRecord } from '../types'
import { useI18n } from '../i18n'

const columnHelper = createColumnHelper<ResourceAccessRecord>()

interface AccessTableProps {
  records: ResourceAccessRecord[]
  totalCount: number
  offset: number
  limit: number
  hasMore: boolean
  onPaginationChange: (offset: number, limit: number) => void
  loading?: boolean
}

export function AccessTable({
  records,
  totalCount,
  offset,
  limit,
  hasMore,
  onPaginationChange,
  loading = false,
}: AccessTableProps) {
  const { t } = useI18n()

  const columns = [
    columnHelper.accessor((row) => row.principal.name, {
      id: 'principal',
      header: t('Principal'),
      cell: (info) => (
        <div>
          <div className="table-primary">{info.row.original.principal.name}</div>
          <div className="table-secondary">
            {t(info.row.original.principal.kind.replace('_', ' '))} via {info.row.original.principal.source}
          </div>
        </div>
      ),
    }),
    columnHelper.accessor('permissions', {
      header: t('Permissions'),
      cell: (info) => (
        <div className="permission-list">
          {info.getValue().map((permission) => (
            <span key={permission} className="permission-chip">
              {t(permission)}
            </span>
          ))}
        </div>
      ),
    }),
    columnHelper.accessor('access_mode', {
      header: t('Mode'),
      cell: (info) => t(info.getValue()),
    }),
    columnHelper.accessor('path_count', {
      header: t('Paths'),
    }),
    columnHelper.accessor('path_complexity', {
      header: t('Complexity'),
      cell: (info) => <span className="kind-pill">{info.getValue()}</span>,
    }),
    columnHelper.accessor('risk_score', {
      header: t('Risk'),
      cell: (info) => <span className="risk-pill">{info.getValue()}</span>,
    }),
  ]

  // TanStack Table exposes imperative helpers that React Compiler intentionally skips memoizing.
  // The table instance remains local to this component and is not passed into memoized children.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: records,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  if (!loading && records.length === 0) {
    return <div className="empty-state">{t('No effective principals for this resource.')}</div>
  }

  const start = totalCount === 0 ? 0 : offset + 1
  const end = totalCount === 0 ? 0 : offset + records.length

  return (
    <div className="table-shell">
      <div className="table-toolbar">
        <div className="table-toolbar__summary">
          <strong>{t('{count} effective principals', { count: totalCount })}</strong>
          <span>
            {loading
              ? t('Loading current page...')
              : t('Showing {start}-{end}', { start, end })}
          </span>
        </div>
        <div className="table-toolbar__actions">
          <label className="table-toolbar__page-size">
            <span>{t('Rows')}</span>
            <select
              value={limit}
              onChange={(event) => onPaginationChange(0, Number(event.target.value))}
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </label>
          <button
            className="table-nav"
            type="button"
            onClick={() => onPaginationChange(Math.max(0, offset - limit), limit)}
            disabled={offset === 0 || loading}
          >
            {t('Previous')}
          </button>
          <button
            className="table-nav"
            type="button"
            onClick={() => onPaginationChange(offset + limit, limit)}
            disabled={!hasMore || loading}
          >
            {t('Next')}
          </button>
        </div>
      </div>
      {loading ? <div className="context-hint">{t('Loading access window...')}</div> : null}
      <table>
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th key={header.id}>
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
