# DAIKAI ROBOT HUB Frontend Style Design

## Design direction

DAIKAI ROBOT HUB uses a dark, technical control-console aesthetic suited to a live
robotics and face-recognition interface. The design prioritizes camera output,
clear system status, compact telemetry, and controls that remain readable at a
distance.

The interface should feel:

- Dark and focused, without pure-black surfaces.
- Technical but approachable.
- Compact enough for monitoring, with comfortable control targets.
- Consistent across recognition, enrollment, and people-management pages.

## Color system

The primary design tokens are declared in `styles.css` under `:root`.

| Token | Value | Usage |
| --- | --- | --- |
| `--bg` | `#07101c` | Main application background |
| `--panel` | `rgba(15, 28, 44, 0.82)` | Reference panel surface |
| `--panel-border` | `rgba(148, 171, 202, 0.14)` | Borders and separators |
| `--muted` | `#8ea0b9` | Secondary labels and helper text |
| `--cyan` | `#55dfd2` | Primary actions, active status, and recognition |
| `--cyan-deep` | `#0da99c` | Focus borders and stronger accents |
| `--danger` | `#ff6f7d` | Errors and unknown-face indicators |

Use cyan sparingly for actions or live/healthy states. Use muted blue-gray for
supporting information. Red should communicate an error, warning, or unknown
recognition result rather than decoration.

## Background and surfaces

The page background combines a deep navy base with subtle teal and blue radial
gradients. Panels use a slightly lighter navy gradient, a low-opacity border,
20 px corners, and a soft shadow. This creates separation without introducing
bright or opaque cards.

Use the shared `.panel` class for major content surfaces. Add a component class
such as `.camera-panel`, `.battery-panel`, or `.speech-panel` for component
padding and internal layout.

## Typography

- **DM Sans** is the default interface font for body text, controls, labels,
  and navigation.
- **Manrope** is used for the brand, headings, large metrics, and prominent
  numeric values.
- Body text is light blue-white rather than pure white.
- Supporting copy uses `--muted`.
- Eyebrow labels use `.eyebrow`: 10 px, uppercase, cyan, bold, and widely
  letter-spaced.
- Panel headings use 21 px Manrope with slightly tightened letter spacing.

Google Fonts are imported at the top of `styles.css`, with system sans-serif
fallbacks when they are unavailable.

## Layout

The main content area is centered with a maximum width of 1440 px. Horizontal
padding uses `clamp()` so spacing scales between small and wide screens.

The recognition workspace uses `.workspace-grid`:

- Main camera area: flexible and visually dominant.
- Telemetry sidebar: minimum width of 290 px.
- Standard gap: 20 px.

The camera keeps a 16:9 aspect ratio. Recognition details below the camera use
a two-column grid for current detections and threshold controls.

## Header and navigation

The top bar is sticky, translucent, and blurred so navigation remains visible
while scrolling. It contains:

- DAIKAI ROBOT HUB brand on the left.
- Page navigation in the center.
- API connection status on the right.

The active navigation item uses a cyan bottom border. Status dots are gray when
inactive and cyan with a glow when online or scanning.

Within the recognition panel, the Standby/Scanning status and the two camera
buttons share the heading row. Camera warnings appear immediately below that
row and above the video.

## Camera and recognition visuals

`CameraStage.jsx` owns the combined camera, detection-summary, and threshold
interface.

- The video area uses a dark background and 14 px rounded corners.
- Known faces use cyan boxes and labels.
- Unknown faces use the danger color.
- Bounding boxes animate briefly between positions to reduce visible jitter.
- An offline placeholder communicates when the robot camera is unavailable.
- Recognition metrics use large cyan numbers for fast scanning.
- The detection list is capped in height and scrolls when necessary.

## Buttons and form controls

All buttons use `.button` for consistent height, padding, typography, radius,
and disabled behavior.

- `.button.primary`: cyan background for the main action.
- `.button.secondary`: subtle transparent background for supporting actions.
- `.button.full`: full-width submission action.
- Disabled controls reduce opacity and remove the active cursor.

Text inputs use a dark translucent background and show a cyan focus ring.
Range controls use the browser-native slider with cyan accent color. Controls
should always have a visible label and clear disabled state.

## Status and feedback

- `.status-pill` displays compact operational state.
- `.error-message` and `.connection-banner` use pale red text and a translucent
  red surface.
- `.success-message` uses mint text and a translucent green surface.
- Battery health and connectivity use the same cyan/green healthy-state
  language as the rest of the application.
- Missing values display an em dash (`—`) rather than zero.

Feedback should appear near the control or content it describes. For example,
camera errors belong between the camera controls and the stream.

## Responsive behavior

At widths below 900 px:

- Recognition and enrollment grids collapse to one column.
- Camera detail cards stack vertically.
- API status is hidden to preserve navigation space.

At widths below 620 px:

- The brand is hidden and navigation spans the available width.
- The camera heading stacks vertically.
- Camera status and buttons use a compact grid.
- Panels use 15 px padding.
- Speech controls and telemetry stacks become single-column layouts.
- Enrollment thumbnails change from six to four columns.

## Extension rules

When adding or changing UI:

1. Reuse the root color tokens instead of introducing nearly identical colors.
2. Use `.panel`, `.panel-heading`, `.button`, and `.muted` before creating new
   variants.
3. Keep the 20 px grid-gap rhythm and use panel padding between 20 and 24 px on
   desktop.
4. Place live state close to the control or data it represents.
5. Reserve cyan for primary actions and active/healthy states.
6. Include behavior for both responsive breakpoints.
7. Keep camera and telemetry information concise so the live image remains the
   visual priority.
