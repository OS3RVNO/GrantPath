import { Search, Sparkles } from 'lucide-react'

import { useI18n } from '../i18n'
import type { SearchResult } from '../types'

interface SearchBoxProps {
  query: string
  loading: boolean
  results: SearchResult[]
  onQueryChange: (value: string) => void
  onSelect: (result: SearchResult) => void
}

export function SearchBox({
  query,
  loading,
  results,
  onQueryChange,
  onSelect,
}: SearchBoxProps) {
  const { t } = useI18n()
  const showResults = query.trim().length > 1

  return (
    <div className="search-box">
      <label className="search-box__label" htmlFor="entity-search">
        {t('Universal search')}
      </label>
      <div className="search-box__shell">
        <Search size={18} />
        <input
          id="entity-search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder={t('Search users, groups, roles, folders, mailboxes, vaults...')}
        />
        <span className="search-box__hint">{t('who • why • what if')}</span>
      </div>

      {showResults ? (
        <div className="search-results">
          {loading ? (
            <div className="search-results__empty">{t('Searching the graph...')}</div>
          ) : results.length === 0 ? (
            <div className="search-results__empty">{t('No matching identity or resource.')}</div>
          ) : (
            results.map((result) => (
              <button
                key={result.entity.id}
                className="search-results__item"
                type="button"
                onClick={() => onSelect(result)}
              >
                <div>
                  <div className="search-results__title">{result.entity.name}</div>
                  <div className="search-results__meta">{t(result.headline)}</div>
                </div>
                <div className="search-results__tags">
                  <span className="kind-pill">{t(result.entity.kind.replace('_', ' '))}</span>
                  {result.keywords.slice(0, 2).map((keyword) => (
                    <span key={keyword} className="search-results__keyword">
                      {keyword}
                    </span>
                  ))}
                </div>
              </button>
            ))
          )}
          <div className="search-results__footer">
            <Sparkles size={14} />
            {t('Select a user or resource to update the live access views.')}
          </div>
        </div>
      ) : null}
    </div>
  )
}
