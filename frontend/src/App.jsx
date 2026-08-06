import { useCallback, useEffect, useState } from 'react'
import { AppHeader } from './components/AppHeader'
import { PageIntro } from './components/PageIntro'
import { EnrollmentPage } from './pages/EnrollmentPage'
import { PeoplePage } from './pages/PeoplePage'
import { FirstPage } from './pages/FirstPage'
import { getHealth, getPeople } from './services/api'


export default function App() {
  const [page, setPage] = useState('recognize')
  const [health, setHealth] = useState(null)
  const [people, setPeople] = useState([])
  const [loadingPeople, setLoadingPeople] = useState(true)
  const [connectionError, setConnectionError] = useState('')

  const refreshData = useCallback(async () => {
    setLoadingPeople(true)
    try {
      const [healthResult, peopleResult] = await Promise.all([getHealth(), getPeople()])
      setHealth(healthResult)
      setPeople(peopleResult.people)
      setConnectionError('')
    } catch (error) {
      setHealth(null)
      setConnectionError(error.message)
    } finally {
      setLoadingPeople(false)
    }
  }, [])

  useEffect(() => {
    refreshData()
  }, [refreshData])

  return (
    <div className="app-shell">
      <AppHeader currentPage={page} health={health} onNavigate={setPage} />
      <main>
        <PageIntro page={page} />
        {connectionError && (
          <div className="connection-banner">
            Cannot reach the FastAPI backend: {connectionError}
          </div>
        )}
        {page === 'recognize' && <FirstPage />}
        {page === 'enroll' && <EnrollmentPage onEnrolled={refreshData} />}
        {page === 'people' && <PeoplePage people={people} loading={loadingPeople} />}
      </main>
      <footer>FaceLens MVP · Images and embeddings stay on this machine</footer>
    </div>
  )
}
