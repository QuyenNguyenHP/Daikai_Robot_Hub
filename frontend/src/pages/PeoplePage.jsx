export function PeoplePage({ people, loading }) {
  return (
    <section className="panel people-panel">
      <div className="panel-heading">
        <div><p className="eyebrow">FACE DATABASE</p><h2>Enrolled people</h2></div>
        <span className="sample-count">{people.length} profiles</span>
      </div>
      {loading && <p className="muted">Loading database…</p>}
      {!loading && people.length === 0 && (
        <div className="empty-state">
          <strong>No people enrolled</strong>
          <span>Create a profile from the Enroll screen.</span>
        </div>
      )}
      <div className="people-list">
        {people.map((person) => (
          <div className="person-row" key={person.name}>
            <div className="avatar large">{person.name[0].toUpperCase()}</div>
            <div className="person-name">
              <strong>{person.name}</strong>
              <span>
                Updated {person.updated_at
                  ? new Date(person.updated_at).toLocaleString()
                  : 'unknown'}
              </span>
            </div>
            <div><strong>{person.samples}</strong><span>latest samples</span></div>
            <div><strong>{person.stored_photos}</strong><span>stored photos</span></div>
          </div>
        ))}
      </div>
    </section>
  )
}
