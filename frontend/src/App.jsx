import { useCallback, useEffect, useState } from 'react'
import { AppHeader } from './components/AppHeader'
import { EnrollmentPage } from './pages/EnrollmentPage'
import { FirstPage } from './pages/FirstPage'
import { SystemServicesPage } from './pages/SystemServicesPage'
import { ObjectDistancePage } from './pages/ObjectDistancePage'
import { getHealth } from './services/api'


export default function App() {
  const [page, setPage] = useState('recognize')
  const [health, setHealth] = useState(null)
  const [connectionError, setConnectionError] = useState('')

  const refreshData = useCallback(async () => {
    try {
      const healthResult = await getHealth()
      setHealth(healthResult)
      setConnectionError('')
    } catch (error) {
      setHealth(null)
      setConnectionError(error.message)
    }
  }, [])

  useEffect(() => {
    refreshData()
  }, [refreshData])

  return (
    <div className="app-shell">
      <AppHeader currentPage={page} health={health} onNavigate={setPage} />
      <main>
        {connectionError && (
          <div className="connection-banner">
            Cannot reach the FastAPI backend: {connectionError}
          </div>
        )}
        {page === 'recognize' && <FirstPage />}
        {page === 'enroll' && <EnrollmentPage onEnrolled={refreshData} />}
        {page === 'object-distance' && <ObjectDistancePage />}
        {page === 'services' && <SystemServicesPage />}
      </main>
      <footer>DAIKAI ROBOT HUB</footer>
    </div>
  )
}
