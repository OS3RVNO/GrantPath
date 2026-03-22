import { useI18n } from '../i18n'

interface LanguageSwitcherProps {
  compact?: boolean
}

export function LanguageSwitcher({ compact = false }: LanguageSwitcherProps) {
  const { locale, setLocale, t, languageOptions } = useI18n()

  return (
    <label className={`language-switcher ${compact ? 'language-switcher--compact' : ''}`}>
      {!compact ? <span>{t('Language')}</span> : null}
      <select
        aria-label={t('Language')}
        value={locale}
        onChange={(event) => setLocale(event.target.value as typeof locale)}
      >
        {languageOptions.map((option) => (
          <option key={option.code} value={option.code}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}
