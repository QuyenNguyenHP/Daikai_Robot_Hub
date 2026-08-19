import drumsLogo from '../../photos/DRUMS_logo.png'


const NAV_ITEMS = [
  ['recognize', 'Console'],
  ['object-distance', 'Object Distance'],
  ['services', 'System Services'],
  ['enroll', 'Enroll'],
]


export function AppHeader({ currentPage, health, onNavigate }) {
  return (
    <header className="topbar">
      <button className="brand" onClick={() => onNavigate('recognize')}>
        <img className="brand-mark" src={drumsLogo} alt="" aria-hidden="true" />
        <span>DAIKAI<small>ROBOT HUB</small></span>
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
        {health ? 'API online' : 'API offline'}
      </div>
    </header>
  )
}
