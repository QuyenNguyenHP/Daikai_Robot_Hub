# FaceLens: Nhan dien khuon mat bang Webcam va Unitree R1

Ung dung web ho tro hai nguon camera:

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

## Cai dat

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt

cd frontend
npm install
cd ..
```

Neu hai model trong `backend/models/` bi thieu:

```bash
python3 -m backend.download_models
```

## Chay voi webcam

Webcam duoc trinh duyet quan ly, backend khong mo `/dev/video*`.

Terminal 1:

```bash
python3 backend/app.py
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Mo `http://localhost:5173`, chon **Device webcam**, sau do bam **Start camera**.

## Chay voi camera Unitree R1

Dung moi truong Python co `unitree_sdk2py` va CycloneDDS hoat dong:

```bash
conda activate unitree
cd /home/r1-edu/Documents/Facial-Reconigtion
export UNITREE_NETWORK_INTERFACE=enxa0cec86d95d6
python3 backend/app.py
```

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

## Dang ky khuon mat

1. Mo man hinh **Enroll**.
2. Nhap ten nguoi.
3. Chon webcam hoac camera robot.
4. Chup 10-20 anh ro, thay doi nhe goc mat va bieu cam.
5. Bam **Create face profile**.

Co the tai anh JPG, PNG hoac WebP thay cho chup camera. Anh va vector duoc luu
vao:

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
which python3
python3 -c "from unitree_sdk2py.go2.video.video_client import VideoClient; print('OK')"
```

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
