const TITLES = {
  recognize: 'See who is there.',
  enroll: 'Teach the system a new face.',
  people: 'Your recognition database.',
}


export function PageIntro({ page }) {
  return (
    <div className="page-intro">
      <div>
        <p className="eyebrow">YUNET + SFACE</p>
        <h1>{TITLES[page]}</h1>
      </div>
      <p>Local face detection and recognition powered by your existing OpenCV models.</p>
    </div>
  )
}
