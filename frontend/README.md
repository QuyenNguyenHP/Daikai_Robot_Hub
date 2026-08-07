# Frontend Structure

The frontend is organized by responsibility so pages, camera behavior, and API
calls can be changed independently.

```text
src/
├── components/                 Reusable visual components
│   ├── AppHeader.jsx
│   ├── CameraStage.jsx
│   ├── RobotControlPanel.jsx
│   ├── RobotSpeechPanel.jsx
│   └── BatteryStatus.jsx
├── hooks/                      Reusable React state/lifecycle logic
│   ├── useBrowserCamera.js
│   └── useCameraSource.js
├── pages/                      Complete application screens
│   ├── EnrollmentPage.jsx
│   └── FirstPage.jsx
├── services/                   Backend and browser-facing operations
│   ├── api.js
│   ├── camera.js
│   └── detections.js
├── App.jsx                     Navigation and shared API state
├── main.jsx                    React entry point
└── styles.css                  Global visual system
```

## Responsibilities

### `components/`

Components receive data and callbacks through props. They should not own page
navigation or enrollment/recognition workflows. Put a component here when it is
reusable or represents a clear piece of UI.

### `pages/`

Each file represents one navigation screen. Pages combine components, hooks,
and services:

- `FirstPage` controls recognition polling, detection results, manual robot
  speech, and automatic recognized-name announcements.
- `EnrollmentPage` controls sample capture, previews, and submission.

### `hooks/`

- `useBrowserCamera` owns `getUserMedia`, media tracks, and browser-camera
  cleanup.
- `useCameraSource` provides one interface for selecting, starting, and stopping
  either the webcam or Unitree camera.

Camera lifecycle changes should normally be made here rather than repeated in
individual pages.

### `services/`

- `api.js` is the only module that knows backend URLs and HTTP endpoint details.
- `camera.js` captures browser video frames and waits for Unitree connection.
- `detections.js` adds image dimensions and smooths bounding boxes.

If a backend endpoint changes, update `services/api.js`; page components should
not contain raw `fetch` calls.

### `App.jsx`

`App` only owns state shared across screens: current page, API health, and
backend connection errors. It does not contain camera or recognition logic.

## Development

```bash
cd frontend
npm install
npm run dev
```

Set a remote backend before starting Vite when required:

```bash
export VITE_API_URL=http://BACKEND_IP:8000
npm run dev
```

Verify a production build:

```bash
npm run build
```

## Adding a page

1. Create `src/pages/NewPage.jsx`.
2. Add its navigation item to `components/AppHeader.jsx`.
3. Render it conditionally from `App.jsx`.

For a larger application, React Router can replace the current small
state-based navigation without changing the existing page components.
