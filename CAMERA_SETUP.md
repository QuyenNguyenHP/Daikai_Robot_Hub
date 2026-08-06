# Huong Dan Test Va Cau Hinh Camera Tren Raspberry Pi 5

Tai lieu nay tong hop rieng phan test camera cho project nhan dien khuon mat.

Ap dung tot nhat cho:

- Raspberry Pi 5
- Raspberry Pi OS 64-bit
- webcam USB UVC thong dung

Neu ban dang dung `USB webcam`, day la quy trinh nen di theo truoc khi chay `enroll.py` hay `recognize.py`.

## 1. Kiem tra he thong da nhan camera chua

Sau khi cam webcam vao Pi, chay:

```bash
ls /dev/video*
```

Neu thay:

```bash
/dev/video0
```

hoac nhieu thiet bi nhu:

```bash
/dev/video0
/dev/video1
```

thi Linux da nhan camera.

## 2. Liet ke dung ten webcam

Lenh nen dung:

```bash
v4l2-ctl --list-devices
```

Neu may chua co `v4l2-ctl`, cai bang:

```bash
sudo apt update
sudo apt install v4l-utils -y
```

Lenh nay giup ban biet:

- ten webcam
- webcam dang map vao `/dev/video0` hay `/dev/video1`
- co bao nhieu thiet bi video dang ton tai

Vi du:

```text
USB Camera: USB Camera (usb-0000:01:00.0-1):
        /dev/video0
        /dev/video1
```

Trong da so truong hop:

- `/dev/video0` la stream chinh
- `/dev/video1` co the la metadata, MJPEG stream phu, hoac che do khac

Nen test lan luot neu khong chac camera nao dung.

## 3. Xem do phan giai va dinh dang webcam ho tro

Chay:

```bash
v4l2-ctl -d /dev/video0 --list-formats-ext
```

Thong tin nay giup ban biet:

- webcam co ho tro `640x480` khong
- webcam co ho tro `1280x720` khong
- co cac format nhu `MJPG`, `YUYV` hay khong

De demo nhan dien khuon mat, nen bat dau voi:

- `640x480`
- `15` den `30 FPS`

## 4. Test camera bang script Python

Project da co san file:

```bash
python3 src/test_camera.py
```

Script nay se:

- mo webcam
- thu dat do phan giai va FPS
- hien anh realtime
- in thong so camera thuc te
- cho phep chup anh test

## 5. Cach chay test camera

### Test mac dinh

```bash
python3 src/test_camera.py
```

### Test webcam khac

```bash
python3 src/test_camera.py --camera-id 1
```

### Test do phan giai cu the

```bash
python3 src/test_camera.py --width 640 --height 480 --fps 20
```

### Thu do phan giai cao hon

```bash
python3 src/test_camera.py --width 1280 --height 720 --fps 30
```

Neu thay giat, lag, hoac CPU cao, quay lai `640x480`.

## 6. Phim tat trong cua so test

Khi cua so camera dang mo:

- nhan `q` de thoat
- nhan `s` de chup va luu 1 anh test vao thu muc `data/camera_test/`

## 7. Cau hinh nen dung cho face recognition

De MVP chay on tren Pi 5, cau hinh khuyen nghi:

- `camera-id = 0`
- `width = 640`
- `height = 480`
- `fps = 20`

Ly do:

- nhe CPU
- detect mat nhanh hon
- de giu realtime on dinh

## 8. Cach doc ket qua test

Sau khi chay script, ban can de y:

- camera co mo duoc hay khong
- hinh co bi den khong
- FPS thuc te co on dinh khong
- thong so `Actual width/height/FPS` co giong cau hinh mong muon khong

Neu camera mo duoc, hinh ro, FPS on, thi co the chuyen sang chay:

```bash
python3 src/enroll.py --name an
python3 src/recognize.py
```

## 9. Loi thuong gap va cach xu ly

### Khong thay `/dev/video0`

Huong xu ly:

- rut ra cam lai webcam
- doi cong USB
- kiem tra nguon cap cho Pi
- thu webcam tren may khac

### `v4l2-ctl --list-devices` khong chay

Huong xu ly:

- cai `v4l-utils`
- kiem tra lai he dieu hanh da cap nhat chua

### Script mo duoc camera nhung man hinh den

Huong xu ly:

- thu `--camera-id 1`
- giam do phan giai
- dong cac ung dung khac dang chiem camera

### Camera bi lag

Huong xu ly:

- giam xuong `640x480`
- dat `fps` ve `15` hoac `20`
- khong vua test camera vua chay them model nang

### Anh mo hoac detect mat kem

Huong xu ly:

- tang anh sang
- giu khoang cach on dinh
- dung webcam co chat luong tot hon

## 10. Quy trinh de xuat truoc khi chay nhan dien mat

1. Kiem tra `/dev/video*`
2. Chay `v4l2-ctl --list-devices`
3. Xem format bang `v4l2-ctl -d /dev/video0 --list-formats-ext`
4. Chay `python3 src/test_camera.py`
5. Chot `camera-id`, `width`, `height`, `fps`
6. Moi chuyen sang `enroll.py` va `recognize.py`
