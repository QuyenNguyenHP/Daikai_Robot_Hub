const NAV_ITEMS = [
  ['recognize', 'Recognize'],
  ['enroll', 'Enroll'],
  ['people', 'People'],
]


export function AppHeader({ currentPage, health, onNavigate }) {
  return (
    <header className="topbar">
      <button className="brand" onClick={() => onNavigate('recognize')}>
        <span className="brand-mark">FL</span>
        <span>FaceLens<small>Recognition console</small></span>
      </button>
      <nav>
        {NAV_ITEMS.map(([page, label]) => (
          <button
            className={currentPage === page ? 'active' : ''}
            key={page}
            onClick={() => onNavigate(page)}
          >
            {label}
          </button>
        ))}
      </nav>
      <div className={`api-status ${health ? 'online' : ''}`}>
        <i />
        {health ? `API online · ${health.people_count} people` : 'API offline'}
      </div>
    </header>
  )
}
