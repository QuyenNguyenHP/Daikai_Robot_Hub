# Huong Dan Chay Project Bang PowerShell Tren Windows

Tai lieu nay huong dan chay project nhan dien khuon mat tren `Windows PowerShell` thay vi `bash` hoac `WSL`.

Tai lieu nay phu hop khi ban muon:

- dung webcam truc tiep tren Windows
- tranh loi camera trong `WSL`
- tao moi truong ao Python bang PowerShell
- chay `test_camera.py`, `enroll.py`, `recognize.py`

## 1. Mo PowerShell dung thu muc project

Mo `PowerShell` va chuyen vao thu muc project:

```powershell
cd "C:\Users\DAIKAI VR\Desktop\Githup Repo\Facial Reconigtion"
```

## 2. Cai Python cho Windows

Neu may chua co Python, tai va cai tu:

```text
https://www.python.org/downloads/windows/
```

Khi cai, can tick:

- `Add python.exe to PATH`
- `Install launcher for all users (recommended)`

Sau do dong PowerShell cu, mo lai va kiem tra:

```powershell
py --version
python --version
```

Neu `py` chay duoc, hay uu tien dung `py`.

## 3. Tao virtual environment

Trong PowerShell, tao moi truong ao:

```powershell
py -m venv .venv
```

## 4. Kich hoat virtual environment

Trong `PowerShell`, dung lenh:

```powershell
.venv\Scripts\Activate.ps1
```

Sau khi kich hoat thanh cong, ban se thay dau nhac lenh co them `(.venv)`.

Khong dung lenh Linux sau trong PowerShell:

```bash
source .venv/bin/activate
```

Vi lenh do chi dung cho `bash` hoac `WSL`.

## 5. Neu PowerShell chan script

Neu gap loi lien quan den `execution policy`, chay lenh nay 1 lan:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Sau do kich hoat lai:

```powershell
.venv\Scripts\Activate.ps1
```

## 6. Cai thu vien cho project

Sau khi da vao `(.venv)`, cai dependency:

```powershell
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
```

File `requirements.txt` hien tai gom:

- `numpy`
- `opencv-contrib-python`
- `requests`

Neu ban gap loi `No module named 'cv2'`, thuong chi can cai lai dependency bang lenh tren.

## 7. Tai model ONNX

Project can 2 model ONNX de detect va recognize khuon mat.

Chay:

```powershell
py src\download_models.py
```

Sau khi thanh cong, thu muc `models\` se co cac file `.onnx`.

## 8. Test webcam tren Windows

Nen test camera truoc khi chay enroll hoac recognize:

```powershell
py src\test_camera.py --camera-id 0
```

Neu ban co nhieu webcam, thu:

```powershell
py src\test_camera.py --camera-id 1
py src\test_camera.py --camera-id 2
```

Neu camera mo duoc, mot cua so preview se hien ra.

Phim tat:

- `q` de thoat
- `s` de chup anh test

Anh test se duoc luu trong:

```text
data\camera_test\
```

## 9. Dang ky khuon mat moi

Vi du dang ky nguoi ten `an`:

```powershell
py src\enroll.py --name an --camera-id 0
```

Cach dung:

- dua mat vao khung hinh
- nhan `s` de luu tung mau
- nhan `q` de thoat

Mac dinh chuong trinh se thu `15` mau.

Neu muon doi camera:

```powershell
py src\enroll.py --name an --camera-id 1
```

Neu muon tang so mau:

```powershell
py src\enroll.py --name an --samples 25
```

## 10. Chay nhan dien realtime

Sau khi da dang ky it nhat 1 nguoi:

```powershell
py src\recognize.py --camera-id 0
```

Neu can doi nguong:

```powershell
py src\recognize.py --camera-id 0 --threshold 0.50
```

Goi y:

- neu nhan nham, tang `threshold`
- neu qua kho nhan dung, giam `threshold`

## 11. Trinh tu chay nhanh tu dau den cuoi

Neu may da cai Python, ban co the chay lan luot:

```powershell
cd "C:\Users\DAIKAI VR\Desktop\Githup Repo\Facial Reconigtion"
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py src\download_models.py
py src\test_camera.py --camera-id 0
py src\enroll.py --name an --camera-id 0
py src\recognize.py --camera-id 0
```

## 12. Loi thuong gap tren Windows

### `python3` khong ton tai

Tren Windows, thuong dung:

```powershell
py
```

hoac:

```powershell
python
```

khong dung `python3` nhu tren Linux.

### `source` khong ton tai

PowerShell khong dung:

```bash
source .venv/bin/activate
```

ma dung:

```powershell
.venv\Scripts\Activate.ps1
```

### `No module named 'cv2'`

Hay dam bao ban da:

- kich hoat dung `(.venv)`
- cai `requirements.txt`
- dang chay cung mot Python environment

Kiem tra nhanh:

```powershell
py -m pip show opencv-contrib-python
py -c "import cv2; print(cv2.__version__)"
```

### Camera mo duoc trong WSL nhung khong doc duoc frame

Neu ban truoc do chay trong `WSL` va gap loi nhu:

```text
select() timeout
Khong doc duoc frame tu camera.
```

hay chuyen sang chay bang `PowerShell` tren Windows. Webcam thuong on dinh hon so voi `WSL`.

## 13. Ghi chu thuc te

Neu muc tieu cua ban la demo nhanh voi webcam USB tren may Windows, thi nen uu tien:

- chay bang `PowerShell`
- dung `py`
- test camera truoc
- xac dinh dung `camera-id` roi moi enroll va recognize
