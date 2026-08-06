da

# MVP Nhan Dien Khuon Mat Cho Raspberry Pi 5 + Webcam

Tai lieu nay huong dan ban trien khai mot MVP nhan dien khuon mat theo huong:

- `OpenCV YuNet` de phat hien khuon mat
- `OpenCV SFace` de trich dac trung va so khop
- `Python` de viet luong xu ly

Huong nay phu hop de demo nhanh tren `Raspberry Pi 5 + webcam USB`.

## 1. Muc tieu cua MVP

MVP nay cho phep:

- Mo webcam va tim khuon mat trong khung hinhpython3 -m pip install -r requirements.txt
- Dang ky mot nguoi moi bang cach chup nhieu mau mat
- Luu vector dac trung cua tung nguoi
- Nhan dien realtime va hien ten neu so khop
- Gan nhan `unknown` neu khong du do tin cay

## 2. Cau truc thu muc

```text
face_recognition_pi5_mvp/
├─ data/
│  ├─ faces/
│  │  └─ <ten_nguoi>/
│  ├─ embeddings.npz
│  └─ metadata.json
├─ backend/
│  ├─ models/
│  ├─ src/
│  │  ├─ common.py
│  │  ├─ download_models.py
│  │  ├─ enroll.py
│  │  └─ recognize.py
│  ├─ face_service.py
│  └─ main.py
├─ frontend/
├─ requirements.txt
└─ README_vi.md
```

## 3. Chuan bi Raspberry Pi 5

Nen dung:

- Raspberry Pi OS 64-bit
- Python 3.11 hoac moi hon
- Webcam USB UVC thong dung

Sau khi cam webcam, kiem tra xem he thong da nhan camera chua. Neu webcam mo duoc trong cac ung dung camera co ban thi co the tiep tuc.

## 4. Cai thu vien

Di chuyen vao thu muc project:

```bash
cd ~/face_recognition_pi5_mvp
```

Tao moi truong ao:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Cap nhat pip:

```bash
python3 -m pip install --upgrade pip
```

Cai phu thuoc:

```bash
python3 -m pip install -r requirements.txt
```

Neu ban gap loi khi cai `opencv-contrib-python`, hay cap nhat he dieu hanh va thu lai. Tren Pi 5 voi Raspberry Pi OS 64-bit moi, cach nay thuong chay on.

## 5. Tai model

Script se tu tai 2 model ONNX tu OpenCV Zoo:

- model detect mat `YuNet`
- model nhan dien `SFace`

Chay:

```bash
python3 backend/src/download_models.py
```

Sau khi tai xong, thu muc `backend/models/` se co 2 file `.onnx`.

## 6. Dang ky khuon mat moi

Co hai cach dang ky: chup truc tiep bang webcam hoac dung cac anh co san.

### Cach 1: Dang ky bang webcam

Vi du dang ky nguoi co ten `an` bang camera co ID `2` (ID mac dinh la `0`):

```bash
python3 backend/src/enroll.py --name an --camera-id 2
```

Cach dung:

- Dua mat vao giua khung hinh
- Nhan phim `s` de luu tung mau
- Moi lan nhan `s`, chuong trinh se cat mat, luu anh va trich vector
- Mac dinh can `15` mau
- Nhan `q` neu muon thoat

Meo de lay mau tot:

- Chup nhieu goc mat khac nhau
- Co mau nhin thang, hoi nghieng trai, hoi nghieng phai
- Doi chut ve bieu cam va khoang cach
- Anh sang deu, khong qua toi

Du lieu sau khi dang ky:

- Anh mat se nam trong `data/faces/an/`
- Vector dac trung se luu trong `data/embeddings.npz`
- Thong tin nguoi dung se luu trong `data/metadata.json`

### Cach 2: Dang ky bang anh co san

Tao mot thu muc rieng chua cac anh cua cung mot nguoi, vi du:

```text
photos/
└─ an/
   ├─ 01.jpg
   ├─ 02.jpg
   ├─ 03.png
   └─ ...
```

Sau do chay:

```bash
python3 backend/src/enroll.py --name an --image-dir photos/an
```

Chuong trinh se doc anh theo thu tu ten file, tim khuon mat lon nhat trong moi
anh va dung toi da `15` anh hop le theo mac dinh. Anh khong doc duoc hoac khong
phat hien thay khuon mat se bi bo qua. Muon dung toi da `25` anh:

```bash
python3 backend/src/enroll.py --name an --image-dir photos/an --samples 25
```

Dinh dang duoc ho tro: `.jpg`, `.jpeg`, `.png`, `.bmp`, `.webp`.

Luu y khi chuan bi anh:

- Tat ca anh trong thu muc phai la cung mot nguoi
- Moi anh nen chi co mot khuon mat; neu co nhieu mat, chuong trinh chi lay mat lon nhat
- Nen co anh nhin thang, nghieng trai, nghieng phai va thay doi nhe bieu cam
- Khuon mat can ro, du sang, khong bi che va khong qua nho
- Nen dung 10-25 anh da dang thay vi nhieu anh gan nhu trung lap

Khong can ket noi webcam khi dung `--image-dir`. Cac anh khuon mat da cat va
vector dac trung van duoc luu vao `data/faces/<ten_nguoi>/`,
`data/embeddings.npz` va `data/metadata.json` nhu cach dang ky bang webcam.
Neu `--name` da ton tai, vector cua nguoi do se duoc thay the bang ket qua cua
lan dang ky moi.

## 7. Chay nhan dien realtime

Sau khi da dang ky it nhat 1 nguoi:

```bash
python3 backend/src/recognize.py
```

Chuong trinh se:

- Mo webcam
- Tim khuon mat trong tung frame
- Trich vector dac trung
- So voi du lieu da dang ky
- Hien ten neu vuot nguong
- Hien `unknown` neu khong du tin cay

Nhan phim `q` de thoat.

## 8. Tuy chinh tham so

### Chon webcam khac

Neu ban co nhieu camera:

```bash
python3 backend/src/enroll.py --name an --camera-id 1
python3 backend/src/recognize.py --camera-id 1
```

### Tang so mau dang ky

```bash
python3 backend/src/enroll.py --name an --samples 25
```

### Dieu chinh nguong nhan dien

Mac dinh:

```bash
python3 backend/src/recognize.py --threshold 0.45
```

Goi y:

- Neu he thong nhan nham, tang nguong len `0.50` hoac `0.55`
- Neu he thong qua kho nhan dung, giam xuong `0.40`

## 9. Quy trinh su dung nhanh

1. Cai thu vien
2. Tai model
3. Dang ky tung nguoi
4. Chay nhan dien realtime

Lenh mau:

```bash
python3 backend/src/download_models.py
python3 backend/src/enroll.py --name an
python3 backend/src/enroll.py --name binh
python3 backend/src/recognize.py
```

## 10. Loi thuong gap

### Webcam khong mo duoc

Huong xu ly:

- Rut ra cam lai webcam
- Thu doi `--camera-id`
- Thu giam do phan giai webcam neu can

### Detect duoc mat nhung nhan sai ten

Huong xu ly:

- Dang ky lai voi nhieu mau hon
- Cai thien anh sang
- Tang `threshold`
- Dung webcam tot hon

### Mat rat nho trong khung hinh

Huong xu ly:

- Di gan camera hon
- Dung khung hinh `640x480` de giam tai va tang kha nang detect

## 11. Goi y nang cap sau MVP

Sau khi MVP chay on, ban co the nang cap:

- Them anti-spoofing de tranh dung anh in
- Them REST API bang FastAPI
- Them systemd de tu khoi dong cung Raspberry Pi
- Them logging va chup anh khi match
- Them co che moi khuon mat can xac nhan qua nhieu frame lien tiep

## 12. Ghi chu quan trong

MVP nay phu hop cho:

- demo
- POC
- robot greeting / human identification co ban

Neu dung cho bai toan an ninh that, ban can bo sung:

- anti-spoofing
- chinh sach bao mat du lieu
- danh gia sai so thuc te
- xu ly tinh huong nhieu nguoi cung luc

## 13. Web app FastAPI + React

Project co them mot web app gom:

- FastAPI backend tai `backend/`
- React + Vite frontend tai `frontend/`
- API tra ket qua JSON gom ten, diem cosine similarity va bounding box
- Man hinh nhan dien realtime bang camera cua trinh duyet
- Man hinh enroll bang upload nhieu anh hoac chup anh tu camera
- Man hinh xem danh sach nhung nguoi da dang ky

Web app dung lai model ONNX va database hien co. Ban khong can enroll lai nhung
nguoi dang co trong `data/embeddings.npz`.

### 13.1 Cai va chay backend

Tai thu muc goc cua project:

```bash
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 backend/app.py
```

Lenh tren la cach ngan gon de chay Uvicorn voi FastAPI. Cach tuong duong:

```bash
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Kiem tra backend:

- Health API: `http://localhost:8000/api/health`
- Swagger API docs: `http://localhost:8000/docs`

API chinh:

```text
GET  /api/health
GET  /api/people
POST /api/recognize   multipart: image, threshold
POST /api/enroll      multipart: name, images
```

Vi du JSON tra ve tu `/api/recognize`:

```json
{
  "image": { "width": 1280, "height": 720 },
  "threshold": 0.45,
  "count": 1,
  "detections": [
    {
      "name": "Mit",
      "confidence": 0.6123,
      "box": { "x": 420, "y": 110, "width": 245, "height": 245 }
    }
  ]
}
```

### 13.2 Cai va chay frontend

Frontend requirements:

- Node.js `20` hoac moi hon
- npm `10` hoac moi hon

Kiem tra phien ban:

```bash
node --version
npm --version
```

Mo terminal thu hai va chay development server:

```bash
cd frontend
npm install
npm run dev
```

Tao production build:

```bash
cd frontend
npm install
npm run build
```

Ket qua build se nam trong `frontend/dist/`. Co the kiem tra production build
tren may local bang:

```bash
npm run preview
```

Mo `http://localhost:5173`, cho phep trinh duyet truy cap camera, sau do:

1. Vao `Enroll` de upload/chup 10-20 anh cho moi nguoi
2. Vao `Recognize`, bam `Start camera`
3. Bam `Start recognition` de gui frame va hien ket qua realtime
4. Dieu chinh threshold neu can; mac dinh la `0.45`

De bounding box di chuyen muot hon, frontend se resize frame nhan dien xuong
toi da `640px`, gui frame moi moi `300ms`, lam muot toa do bang IoU + exponential
smoothing va noi suy CSS trong `180ms`. Neu Raspberry Pi bi CPU cao, co the tang
chu ky scan trong `frontend/src/App.jsx` tu `300` len `400` hoac `500` ms.

Neu backend nam tren may khac, tao `frontend/.env`:

```dotenv
VITE_API_URL=http://192.168.1.50:8000
```

Neu frontend chay tu mot origin khac, dat danh sach CORS truoc khi chay backend:

```bash
export FR_CORS_ORIGINS=http://localhost:5173,http://192.168.1.50:5173
```

Luu y: phan lon trinh duyet chi cho phep `getUserMedia` tren `localhost` hoac
HTTPS. Khi truy cap Raspberry Pi bang dia chi IP tu may khac, nen cau hinh HTTPS
bang reverse proxy (vi du Caddy hoac Nginx) cho ban production.

### 13.3 Gioi han va bao mat

- Moi anh upload toi da 10 MB; moi lan enroll toi da 30 anh
- Backend chi luu anh khuon mat da cat, embedding trung binh va metadata
- Neu enroll lai cung ten, embedding cu se duoc thay the; anh cat cu van duoc giu
- API hien chua co dang nhap, phan quyen hay rate limiting
- Khong nen mo port backend truc tiep ra Internet
- Can co su dong y cua nguoi dung va chinh sach luu/xoa du lieu khuon mat
