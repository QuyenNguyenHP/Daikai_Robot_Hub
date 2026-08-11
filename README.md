# Daikai Robot Hub: Control the Unitree R1 Robot with Face Recognition

Daikai Robot Hub is a local robot operations and face-recognition application
built with FastAPI, React, OpenCV YuNet, and OpenCV SFace. It combines:

- Unitree R1 camera access through Unitree SDK2
- face enrollment and recognition
- robot speech playback
- robot battery monitoring
- bounded locomotion control

The application uses one camera source:

- **Unitree R1 camera**: the robot camera, read by the backend through
  Unitree SDK2.

The robot camera shares the same YuNet, SFace, and face database stored in
`data/`. The main interface also lets you:

- send English speech to the robot speaker
- view live battery telemetry
- send safe movement commands
- enable automatic spoken name greetings when recognition confidence reaches
  70% or higher

## Main structure

```text
backend/           FastAPI backend, face recognition, robot control, and robot services
frontend/          React frontend for robot camera, robot status, and control panels
data/              images, embeddings, and metadata
reference_script/  standalone robot test scripts
```

Details for each backend Python file are in [`backend/README.md`](backend/README.md).
Instructions for LAN access through Apache2 are in
[`APACHE2_LAN_SETUP_vi.md`](APACHE2_LAN_SETUP_vi.md).

## General frontend style

The frontend uses a dark, futuristic operations-dashboard style. The visual
language is restrained rather than decorative: deep navy backgrounds, layered
translucent panels, fine low-contrast borders, compact telemetry labels, and a
bright cyan accent for interactive and live states. The complete implementation
is in [`frontend/src/styles.css`](frontend/src/styles.css).

### Design foundation

- **Typography:** use **DM Sans** for body text, controls, and labels. Use
  **Manrope** at weights 500-700 for headings, metrics, and other prominent
  values. Headings use slightly tight letter spacing; small labels use wide
  letter spacing and often uppercase text.
- **Page background:** start with `#07101c` and add subtle blue/cyan radial
  gradients. This creates depth without competing with application content.
- **Surfaces:** use dark navy translucent gradients, a `20px` radius, a faint
  cool-gray border, and a soft downward shadow. Nested surfaces are darker,
  flatter, and normally use an `8-12px` radius.
- **Accent color:** cyan communicates primary actions, focus, connectivity,
  active navigation, recognition, and live data. Do not use it on every piece
  of text; the limited use of cyan preserves its meaning.
- **Semantic color:** coral red communicates errors, unknown detections, stop
  actions, and safety warnings. Soft green is reserved for successful results
  or healthy states.
- **Text hierarchy:** use near-white for important content, blue-gray for
  supporting text, and small uppercase cyan text for section eyebrows.

Core colors can be copied into another project as CSS custom properties:

```css
:root {
  font-family: 'DM Sans', system-ui, sans-serif;
  color: #e7edf7;
  background: #07101c;

  --bg: #07101c;
  --panel: rgba(15, 28, 44, 0.82);
  --panel-border: rgba(148, 171, 202, 0.14);
  --muted: #8ea0b9;
  --cyan: #55dfd2;
  --cyan-deep: #0da99c;
  --danger: #ff6f7d;
}
```

The main surface treatment is:

```css
.panel {
  background: linear-gradient(
    145deg,
    rgba(17, 32, 50, 0.95),
    rgba(11, 23, 38, 0.9)
  );
  border: 1px solid var(--panel-border);
  border-radius: 20px;
  box-shadow: 0 22px 60px rgba(0, 0, 0, 0.18);
}
```

### Layout and spacing

Content is centered in a `1440px` maximum-width container with fluid horizontal
padding (`clamp(18px, 4vw, 64px)`). Desktop pages use CSS Grid for a wide main
workspace and a narrower status/control column. Keep `20px` between major
panels and approximately `20-24px` of internal panel padding. Use Flexbox for
small one-dimensional groups such as headings, actions, status rows, and
navigation.

The top bar is sticky and slightly translucent with an `18px` backdrop blur.
This glass effect should be limited to persistent navigation and modal
backdrops; normal content stays readable through more opaque panel surfaces.

### Reusable component conventions

- **Buttons:** `42px` minimum height, `10px` radius, bold `13px` text, and a
  subtle `0.2s` transition. Primary buttons use cyan with very dark text;
  secondary buttons use a faint gray-blue fill and border. Disabled controls
  reduce opacity and replace the pointer cursor.
- **Inputs:** `46px` height, `10px` radius, dark translucent fill, and a subtle
  border. Focus changes the border to deep cyan and adds a low-opacity cyan
  focus ring.
- **Status pills:** use fully rounded capsules, compact `11px` text, a faint
  background, and a small circular indicator. A live indicator becomes cyan
  and receives a restrained glow.
- **Telemetry:** show important numbers in Manrope and supporting labels in
  small, widely spaced DM Sans. Definition lists and compact two-column grids
  work well for dense metrics.
- **Feedback:** display errors in coral, successes in soft green, and keep both
  on low-opacity tinted backgrounds with matching borders.
- **Motion:** keep animation functional and short. The current interface uses
  small hover lifts, color fades, status glows, and linear tracking-box
  movement rather than large decorative animation.

### Responsive behavior

The design uses two breakpoints:

- At `900px` and below, major two-column workspaces become one column. Supporting
  side panels may remain in two columns when space permits, and secondary API
  status is hidden.
- At `620px` and below, the header and all supporting panels become one column,
  navigation stretches across the width, panel padding reduces to `15px`, and
  action/form rows stack or become equal-width grids.

When reusing this style, preserve the hierarchy of **page background -> panel ->
nested surface**, the restrained cyan accent, and the `20px` spacing rhythm.
Application-specific selectors such as camera, battery, face-box, and movement
controls can be omitted; the root tokens, `.panel`, `.button`, `.text-input`,
status, feedback, layout, and responsive rules form the reusable core.

## Architecture

```text
Unitree R1 camera  -> Unitree SDK2 -> RobotCamera ------+
                                                        +-> FastAPI -> YuNet -> SFace
Unitree R1 battery -> DDS topic -> RobotBattery -------+
Unitree R1 motion  -> RobotControl API ----------------+
Unitree R1 speaker -> RobotSpeech API -----------------+
```

The robot camera, battery, motion, and speaker integrations are handled by the
backend because the browser does not connect to Unitree DDS directly.

## Requirements

- Python 3.10 when using Unitree SDK2 Python.
- Node.js 20 or newer, with Node.js 22 recommended.
- npm 10 or newer.
- Unitree SDK2 Python and a network interface connected to the robot when using
  robot mode.
- `pico2wave` as the preferred TTS engine, with `espeak` fallback, plus
  `ffmpeg` or `sox` when using robot speech.

## Installation

If the machine does not have `python3.10` yet, for example on Debian Trixie or
Raspberry Pi OS, install Python 3.10 first using step 1 in
**Install Unitree SDK2 Python** below before continuing.

### Install Node.js and npm if needed

Check whether Node.js and npm are already installed:

```bash
node --version
npm --version
```

If one of them is missing, install Node.js 22 using `nvm`. This works on both
Debian and Ubuntu, and npm is installed together with Node.js:

```bash
sudo apt update
sudo apt install -y curl

curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

command -v nvm
nvm install 22
nvm alias default 22

node --version
npm --version
```

`command -v nvm` should print `nvm`. If it says `nvm: command not found`, close
the terminal, open a new one, and run the checks again.

### Install backend and frontend dependencies

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd frontend
npm install
cd ..
```

If the two models in `backend/models/` are missing:

```bash
python -m backend.download_models
```

### Install `pico2wave` for robot speech

Robot speech prefers `pico2wave`. If it is not installed yet, install it on
Debian, Ubuntu, or Raspberry Pi OS with:

```bash
sudo apt update
sudo apt install -y libttspico-utils
```

Check that the command is available:

```bash
which pico2wave
pico2wave --help
```

To let the backend convert audio for robot playback, also install one of:

```bash
sudo apt install -y ffmpeg
```

or:

```bash
sudo apt install -y sox
```

Quick `pico2wave` test:

```bash
pico2wave -l=en-US -w /tmp/pico-test.wav "Hello from Daikai Robot Hub"
ls -lh /tmp/pico-test.wav
```

If the WAV file is created successfully, text-to-speech is ready for backend
use.

## Run the frontend locally

Terminal 1:

```bash
python backend/app.py
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`, choose **Unitree R1 camera**, then click
**Start camera**.

## Install Unitree SDK2 Python

> **Requirement:** use **Python 3.10**. Check the version before installing:
>
> ```bash
> python3.10 --version
> ```

### 1. Install Python 3.10 and system packages

Check the operating system:

```bash
cat /etc/os-release
```

Choose **one** of the following installation paths.

#### Option A - Ubuntu 22.04 LTS

Ubuntu 22.04 already provides Python 3.10 in the repository. Install it with
`apt`:

```bash
cd ~

sudo apt update
sudo apt install -y \
    python3.10 \
    python3.10-venv \
    python3.10-dev \
    python3-pip \
    git \
    cmake \
    build-essential

python3.10 --version
```

If Ubuntu reports `Unable to locate package python3.10`, do not add Debian
repositories to Ubuntu. Use **Option B** and build Python 3.10 from source.

#### Option B - Debian Trixie, Raspberry Pi OS, or Ubuntu without Python 3.10

Debian Trixie uses Python 3.13 by default and does not include
`python3.10`, `python3.10-venv`, or `python3.10-dev` in the default
repository. Install the build dependencies and build a separate Python 3.10
from source. `make altinstall` does not overwrite the system `python3`.

```bash
cd ~

sudo apt update
sudo apt install -y \
    git \
    cmake \
    build-essential \
    wget \
    xz-utils \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncurses-dev \
    libgdbm-dev \
    liblzma-dev \
    libffi-dev \
    libexpat1-dev \
    uuid-dev

cd ~
wget https://www.python.org/ftp/python/3.10.20/Python-3.10.20.tar.xz
echo "de6517421601e39a9a3bc3e1bc4c7b2f239297423ee05e282598c83ec0647505  Python-3.10.20.tar.xz" \
    | sha256sum --check

tar -xf Python-3.10.20.tar.xz
cd Python-3.10.20
./configure --with-ensurepip=install
make -j"$(nproc)"
sudo make altinstall

python3.10 --version
```

The expected result is `Python 3.10.20`. Do not change the system `python3`
symlink to Python 3.10.

### 2. Build Cyclone DDS

```bash
cd ~

git clone \
    --branch releases/0.10.x \
    https://github.com/eclipse-cyclonedds/cyclonedds.git

cd ~/cyclonedds
mkdir -p build install
cd build

cmake .. \
    -DCMAKE_INSTALL_PREFIX="$HOME/cyclonedds/install"

cmake --build . --target install -j"$(nproc)"
```

### 3. Download Unitree SDK2 Python

```bash
cd ~

git clone \
    https://github.com/unitreerobotics/unitree_sdk2_python.git

cd ~/unitree_sdk2_python
```

### 4. Create and activate the Python 3.10 virtual environment

Create `.venv` directly inside the Unitree SDK2 Python project:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
```

The virtual environment is created at:

```text
~/unitree_sdk2_python/.venv
```

After activation, the terminal should look similar to:

```text
(.venv) user@computer:~/unitree_sdk2_python$
```

Confirm that `.venv` uses Python 3.10, then upgrade the install tools:

```bash
python --version
python -m pip install --upgrade pip setuptools wheel
```

### 5. Export Cyclone DDS paths

Run these commands in the terminal where `.venv` is active:

```bash
export CYCLONEDDS_HOME="$HOME/cyclonedds/install"
export CMAKE_PREFIX_PATH="$CYCLONEDDS_HOME:$CMAKE_PREFIX_PATH"
export LD_LIBRARY_PATH="$CYCLONEDDS_HOME/lib:$LD_LIBRARY_PATH"
```

### 6. Install Unitree SDK2 Python

From `~/unitree_sdk2_python`, run:

```bash
python -m pip install -e .
```

Check that the SDK was installed successfully:

```bash
python -c "from unitree_sdk2py.go2.video.video_client import VideoClient; print('Unitree SDK2 Python OK')"
```

To run the robot camera, the Daikai Robot Hub backend and Unitree SDK2 must live in the
same Python environment. While the Unitree `.venv` is still active, install the
Daikai Robot Hub dependencies as well:

```bash
cd /home/r1-edu/Documents/Facial-Reconigtion
python -m pip install -r requirements.txt
```

Every time you open a new terminal, activate `.venv` again and export the
Cyclone DDS environment variables before starting the app.

## Run with the Unitree R1 camera

Find the network interface connected to the robot:

```bash
ip link
```

Activate the environment where Unitree SDK2 was installed, export Cyclone DDS
and the network interface, then start the backend:

```bash
source ~/unitree_sdk2_python/.venv/bin/activate

export CYCLONEDDS_HOME="$HOME/cyclonedds/install"
export CMAKE_PREFIX_PATH="$CYCLONEDDS_HOME:$CMAKE_PREFIX_PATH"
export LD_LIBRARY_PATH="$CYCLONEDDS_HOME/lib:$LD_LIBRARY_PATH"
export UNITREE_NETWORK_INTERFACE=enxa0cec86d95d6

cd /home/r1-edu/Documents/Facial-Reconigtion
python backend/app.py
```

Replace `enxa0cec86d95d6` with the interface name found from `ip link`. Do not
run multiple Uvicorn workers in robot mode because Unitree DDS and the camera
client are shared resources inside one process.

Check the camera:

```bash
curl -s http://127.0.0.1:8000/api/robot/status | python3 -m json.tool
```

A successful connection looks like:

```json
{
  "state": "connected",
  "connected": true,
  "frame_sequence": 100,
  "error": null
}
```

Then choose **Unitree R1 camera** in the UI and click **Start camera**.

## Robot API

The backend provides these endpoints:

| Endpoint                                     | Purpose                                       |
| -------------------------------------------- | --------------------------------------------- |
| `GET /api/robot/status`                    | View robot camera configuration and state     |
| `POST /api/robot/connect`                  | Start the shared Unitree camera client        |
| `GET /api/robot/snapshot`                  | Get the newest robot JPEG                     |
| `GET /api/robot/stream`                    | View the live MJPEG stream                    |
| `POST /api/robot/recognize?threshold=0.45` | Recognize faces in the newest frame           |
| `GET /api/robot/battery`                   | View the latest battery telemetry             |
| `GET /api/robot/control/status`            | View locomotion control status                |
| `GET /api/robot/mode`                      | Query the current robot FSM mode              |
| `POST /api/robot/control`                  | Send a bounded locomotion command             |
| `GET /api/robot/speech/status`             | Check speech tool availability and busy state |
| `POST /api/robot/speak`                    | Send English speech to the robot speaker      |

The HTTP API can also be used by external clients if needed.

For backend implementation details, endpoint behavior, and recommended launch
modes, see [`backend/README.md`](backend/README.md).

## Face enrollment

1. Open the **Enroll** screen.
2. Enter the person's name.
3. Use the Unitree R1 camera to capture samples.
4. Capture 10-20 clear images with slight pose and expression changes.
5. Click **Create face profile**.

Images and vectors are stored in:

```text
data/faces/<name>/
data/embeddings.npz
data/metadata.json
```

## Recognition

1. Open the **Recognize** screen.
2. Use the Unitree R1 camera.
3. Click **Start camera**.
4. Click **Start recognition**.

The default threshold is `0.45`. Raise it to reduce false positives, or lower
it if the system struggles to recognize already enrolled people.

## Common issues

### `unitree_sdk2py` cannot be imported

Check that you are using the correct Python environment:

```bash
which python
python --version
python -c "from unitree_sdk2py.go2.video.video_client import VideoClient; print('OK')"
```

`which python` should point to `~/unitree_sdk2_python/.venv/bin/python` when
running the robot camera mode.

### Robot state is `not_configured`

Set the environment variable before starting the backend:

```bash
export UNITREE_NETWORK_INTERFACE=enxa0cec86d95d6
```

### Frontend on another machine

Set the backend address before starting Vite:

```bash
export VITE_API_URL=http://BACKEND_IP:8000
```

If needed, open CORS on the backend:

```bash
export FR_CORS_ORIGINS=http://FRONTEND_IP:5173
```

### The robot camera does not start

Check that:

- `UNITREE_NETWORK_INTERFACE` is set correctly;
- the backend is running in the Python environment that contains
  `unitree_sdk2py`;
- the robot is reachable on the selected interface;
- `GET /api/robot/status` reports a configured or connected state.
