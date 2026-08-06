# MVP Nhan Dien Khuon Mat Cho Raspberry Pi 5 + Webcam

Tai lieu nay huong dan ban trien khai mot MVP nhan dien khuon mat theo huong:

- `OpenCV YuNet` de phat hien khuon mat
- `OpenCV SFace` de trich dac trung va so khop
- `Python` de viet luong xu ly

Huong nay phu hop de demo nhanh tren `Raspberry Pi 5 + webcam USB`.

## 1. Muc tieu cua MVP

MVP nay cho phep:

- Mo webcam va tim khuon mat trong khung hinh
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
├─ models/
├─ src/
│  ├─ common.py
│  ├─ download_models.py
│  ├─ enroll.py
│  └─ recognize.py
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
python3 src/download_models.py
```

Sau khi tai xong, thu muc `models/` se co 2 file `.onnx`.

## 6. Dang ky khuon mat moi

Vi du dang ky nguoi co ten `an`:

```bash
python3 src/enroll.py --name an
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

## 7. Chay nhan dien realtime

Sau khi da dang ky it nhat 1 nguoi:

```bash
python3 src/recognize.py
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
python3 src/enroll.py --name an --camera-id 1
python3 src/recognize.py --camera-id 1
```

### Tang so mau dang ky

```bash
python3 src/enroll.py --name an --samples 25
```

### Dieu chinh nguong nhan dien

Mac dinh:

```bash
python3 src/recognize.py --threshold 0.45
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
python3 src/download_models.py
python3 src/enroll.py --name an
python3 src/enroll.py --name binh
python3 src/recognize.py
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
