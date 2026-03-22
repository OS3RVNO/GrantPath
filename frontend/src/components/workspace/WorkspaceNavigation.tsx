import { useI18n } from '../../i18n'

interface WorkspaceViewItem {
  id: string
  label: string
  title: string
  description: string
}

interface WorkspaceTabItem {
  id: string
  label: string
}

interface WorkspaceNavigationProps {
  activeView: WorkspaceViewItem
  views: WorkspaceViewItem[]
  activeViewId: string
  onSelectView: (viewId: string) => void
  secondaryTabs: WorkspaceTabItem[]
  activeSecondaryTabId?: string | null
  onSelectSecondaryTab: (tabId: string) => void
}

export function WorkspaceNavigation({
  activeView,
  views,
  activeViewId,
  onSelectView,
  secondaryTabs,
  activeSecondaryTabId,
  onSelectSecondaryTab,
}: WorkspaceNavigationProps) {
  const { t } = useI18n()

  return (
    <aside className="workspace-nav">
      <article className="workspace-menu">
        <div>
          <div className="eyebrow">{t('Navigation')}</div>
          <h2>{activeView.label}</h2>
          <p className="admin-copy">{activeView.description}</p>
        </div>
        <nav className="workspace-menu__list" aria-label={t('Workspace sections')}>
          {views.map((view) => (
            <button
              key={view.id}
              type="button"
              className={`workspace-menu__item ${
                activeViewId === view.id ? 'workspace-menu__item--active' : ''
              }`}
              onClick={() => onSelectView(view.id)}
            >
              <span className="workspace-menu__label">{view.label}</span>
              <span className="workspace-menu__copy">{view.title}</span>
            </button>
          ))}
        </nav>
      </article>

      {secondaryTabs.length ? (
        <article className="workspace-menu workspace-menu--subnav">
          <div>
            <div className="eyebrow">{t('Section Menu')}</div>
            <h2>{t('Open a module')}</h2>
          </div>
          <div className="workspace-subtabs workspace-subtabs--stacked">
            {secondaryTabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`workspace-subtab ${
                  activeSecondaryTabId === tab.id ? 'workspace-subtab--active' : ''
                }`}
                onClick={() => onSelectSecondaryTab(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </article>
      ) : null}
    </aside>
  )
}
