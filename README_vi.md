# FaceLens: Nhan dien khuon mat bang Webcam va Unitree R1

FaceLens la ung dung dang ky va nhan dien khuon mat chay local, duoc xay dung
bang FastAPI, React, OpenCV YuNet va OpenCV SFace. Ung dung ho tro hai nguon
camera:

- **Device webcam**: webcam cua may dang mo trinh duyet.
- **Unitree R1 camera**: camera robot, duoc backend doc qua Unitree SDK2.

Ca hai nguon dung chung YuNet, SFace va co so du lieu khuon mat trong `data/`.
Trang dau tien cung cho phep nhap cau tieng Anh de robot noi. Nut **Auto name**
se bat/tat viec robot chao ten nguoi khi do tin cay nhan dien dat tu 70%.

## Cau truc chinh

```text
backend/       FastAPI, xu ly khuon mat va camera robot
frontend/      React, webcam trinh duyet va giao dien
data/          anh, embeddings va metadata
reference_script/  script robot doc lap de test
```

Chi tiet tung file Python backend nam tai [`backend/README.md`](backend/README.md).
Huong dan cho laptop khac trong cung mang truy cap qua Apache2 nam tai
[`APACHE2_LAN_SETUP_vi.md`](APACHE2_LAN_SETUP_vi.md).

## Kien truc

```text
Webcam trinh duyet -> Tai anh JPEG --------+
                                           +-> FastAPI -> YuNet -> SFace
Unitree R1 -> Unitree SDK -> FastAPI ------+
```

Webcam duoc truy cap bang `navigator.mediaDevices.getUserMedia()`. Camera robot
duoc mot `VideoClient` dung chung tren backend doc qua Unitree DDS; trinh duyet
khong ket noi truc tiep voi DDS.

## Yeu cau

- Python 3.10 khi su dung Unitree SDK2 Python.
- Node.js 20 tro len (khuyen nghi Node.js 22).
- npm 10 tro len.
- Unitree SDK2 Python va card mang ket noi voi robot khi dung che do robot.
- `pico2wave` (uu tien, fallback sang eSpeak) va `ffmpeg` hoac `sox` neu dung
  tinh nang robot noi.

## Cai dat

Neu may chua co lenh `python3.10` (vi du Debian Trixie/Raspberry Pi OS), hay
cai Python 3.10 theo buoc 1 trong muc **Cai dat Unitree SDK2 Python** ben duoi
truoc khi tiep tuc.

### Cai Node.js va npm neu chua co

Kiem tra Node.js va npm:

```bash
node --version
npm --version
```

Neu mot trong hai lenh khong ton tai, cai Node.js 22 bang `nvm`. Cach nay dung
duoc tren ca Debian va Ubuntu, dong thoi npm se duoc cai kem Node.js:

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

Lenh `command -v nvm` phai in ra `nvm`. Neu bao `nvm: command not found`, dong
terminal, mo terminal moi va chay lai cac lenh kiem tra.

### Cai dependency cua backend va frontend

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cd frontend
npm install
cd ..
```

Neu hai model trong `backend/models/` bi thieu:

```bash
python -m backend.download_models
```

## Chay voi webcam

Webcam duoc trinh duyet quan ly, backend khong mo `/dev/video*`.

Terminal 1:

```bash
python backend/app.py
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Mo `http://localhost:5173`, chon **Device webcam**, sau do bam **Start camera**.

## Cai dat Unitree SDK2 Python

> **Yeu cau:** su dung **Python 3.10**. Kiem tra phien ban truoc khi cai dat:
>
> ```bash
> python3.10 --version
> ```

### 1. Cai dat Python 3.10 va cac goi he thong

Kiem tra he dieu hanh dang su dung:

```bash
cat /etc/os-release
```

Chon **mot** trong hai cach cai dat sau.

#### Option A - Ubuntu 22.04 LTS

Ubuntu 22.04 cung cap san Python 3.10 trong repository. Cai dat bang `apt`:

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

Neu Ubuntu bao `Unable to locate package python3.10`, khong them repository cua
Debian vao Ubuntu. Hay dung **Option B** de build Python 3.10 tu source.

#### Option B - Debian Trixie, Raspberry Pi OS hoac Ubuntu khong co Python 3.10

Debian Trixie dung Python 3.13 mac dinh va khong co cac goi `python3.10`,
`python3.10-venv`, `python3.10-dev` trong repository mac dinh. Cai cac thu vien
build, sau do build Python 3.10 rieng tu source. Lenh `make altinstall` khong ghi
de len lenh `python3` cua he thong.

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

Ket qua mong doi la `Python 3.10.20`. Khong thay doi symlink `python3` cua he
thong sang Python 3.10.

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

### 3. Tai Unitree SDK2 Python

```bash
cd ~

git clone \
    https://github.com/unitreerobotics/unitree_sdk2_python.git

cd ~/unitree_sdk2_python
```

### 4. Tao va kich hoat moi truong ao Python 3.10

Tao `.venv` ngay trong thu muc du an Unitree SDK2 Python:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
```

Moi truong ao duoc tao tai:

```text
~/unitree_sdk2_python/.venv
```

Sau khi kich hoat, terminal se hien thi tuong tu:

```text
(.venv) user@computer:~/unitree_sdk2_python$
```

Xac nhan `.venv` dang dung Python 3.10, sau do nang cap cac cong cu cai dat:

```bash
python --version
python -m pip install --upgrade pip setuptools wheel
```

### 5. Khai bao duong dan Cyclone DDS

Chay cac lenh sau trong terminal dang kich hoat `.venv`:

```bash
export CYCLONEDDS_HOME="$HOME/cyclonedds/install"
export CMAKE_PREFIX_PATH="$CYCLONEDDS_HOME:$CMAKE_PREFIX_PATH"
export LD_LIBRARY_PATH="$CYCLONEDDS_HOME/lib:$LD_LIBRARY_PATH"
```

### 6. Cai dat Unitree SDK2 Python

Tu thu muc `~/unitree_sdk2_python`, chay:

```bash
python -m pip install -e .
```

Kiem tra SDK da duoc cai dat thanh cong:

```bash
python -c "from unitree_sdk2py.go2.video.video_client import VideoClient; print('Unitree SDK2 Python OK')"
```

De chay camera robot, backend FaceLens va Unitree SDK2 phai nam trong cung mot
moi truong Python. Khi `.venv` cua Unitree van dang duoc kich hoat, cai them cac
dependency cua FaceLens:

```bash
cd /home/r1-edu/Documents/Facial-Reconigtion
python -m pip install -r requirements.txt
```

Moi lan mo terminal moi, can kich hoat lai `.venv` va khai bao cac bien moi
truong Cyclone DDS truoc khi chay ung dung.

## Chay voi camera Unitree R1

Tim ten card mang dang ket noi voi robot:

```bash
ip link
```

Kich hoat moi truong da cai Unitree SDK2, khai bao Cyclone DDS va card mang,
sau do khoi dong backend:

```bash
source ~/unitree_sdk2_python/.venv/bin/activate

export CYCLONEDDS_HOME="$HOME/cyclonedds/install"
export CMAKE_PREFIX_PATH="$CYCLONEDDS_HOME:$CMAKE_PREFIX_PATH"
export LD_LIBRARY_PATH="$CYCLONEDDS_HOME/lib:$LD_LIBRARY_PATH"
export UNITREE_NETWORK_INTERFACE=enxa0cec86d95d6

cd /home/r1-edu/Documents/Facial-Reconigtion
python backend/app.py
```

Thay `enxa0cec86d95d6` bang ten card mang tim duoc tu `ip link`. Khong chay
nhieu Uvicorn worker trong che do robot vi Unitree DDS va camera client la tai
nguyen dung chung trong mot process.

Kiem tra camera:

```bash
curl -s http://127.0.0.1:8000/api/robot/status | python3 -m json.tool
```

Ket noi dung se co:

```json
{
  "state": "connected",
  "connected": true,
  "frame_sequence": 100,
  "error": null
}
```

Sau do tai giao dien chon **Unitree R1 camera** va bam **Start camera**.

## Robot API

Backend cung cap cac endpoint sau:

| Endpoint                                     | Chuc nang                                  |
| -------------------------------------------- | ------------------------------------------ |
| `GET /api/robot/status`                    | Xem cau hinh va trang thai ket noi camera  |
| `POST /api/robot/connect`                  | Khoi dong Unitree camera client dung chung |
| `GET /api/robot/snapshot`                  | Lay anh JPEG moi nhat tu robot             |
| `GET /api/robot/stream`                    | Xem luong MJPEG truc tiep                  |
| `POST /api/robot/recognize?threshold=0.45` | Nhan dien khuon mat trong frame moi nhat   |

Nhung endpoint upload anh ban dau van duoc giu nguyen, nen che do webcam va cac
API client ben ngoai van tuong thich.

## Dang ky khuon mat

1. Mo man hinh **Enroll**.
2. Nhap ten nguoi.
3. Chon webcam hoac camera robot.
4. Chup 10-20 anh ro, thay doi nhe goc mat va bieu cam.
5. Bam **Create face profile**.

Co the tai anh JPG, PNG hoac WebP va ket hop chung voi cac mau chup tu camera.
Anh va vector duoc luu vao:

```text
data/faces/<ten>/
data/embeddings.npz
data/metadata.json
```

## Nhan dien

1. Mo man hinh **Recognize**.
2. Chon nguon camera.
3. Bam **Start camera**.
4. Bam **Start recognition**.

Nguong mac dinh la `0.45`. Tang nguong de giam nhan nham; giam nguong neu he
thong qua kho nhan ra nguoi da dang ky.

## Loi thuong gap

### `unitree_sdk2py` khong import duoc

Kiem tra dung Python environment:

```bash
which python
python --version
python -c "from unitree_sdk2py.go2.video.video_client import VideoClient; print('OK')"
```

Duong dan tu `which python` phai tro den
`~/unitree_sdk2_python/.venv/bin/python` khi chay camera robot.

### Robot `not_configured`

Dat bien moi truong truoc khi khoi dong backend:

```bash
export UNITREE_NETWORK_INTERFACE=enxa0cec86d95d6
```

### Frontend o may khac

Dat dia chi backend truoc khi khoi dong Vite:

```bash
export VITE_API_URL=http://BACKEND_IP:8000
```

Neu can, mo CORS tren backend:

```bash
export FR_CORS_ORIGINS=http://FRONTEND_IP:5173
```

### Webcam bi tu choi

Cho phep camera trong trinh duyet. `getUserMedia()` can `localhost` hoac HTTPS
khi ung dung khong chay tren may local.
