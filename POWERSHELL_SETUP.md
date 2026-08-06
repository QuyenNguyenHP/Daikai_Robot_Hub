# Chay FaceLens bang PowerShell tren Windows

Tai lieu nay huong dan chay che do webcam cua ung dung web tren Windows.
Camera Unitree R1 can backend chay tren may da cai Unitree SDK2 va ket noi mang
voi robot.

## Cai dat

Mo PowerShell tai thu muc project:

```powershell
cd "C:\path\to\Facial-Reconigtion"
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
py -m pip install -r requirements.txt

cd frontend
npm install
cd ..
```

Neu PowerShell chan script kich hoat:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Neu model bi thieu:

```powershell
py -m backend.download_models
```

## Khoi dong

Terminal PowerShell thu nhat:

```powershell
.venv\Scripts\Activate.ps1
py backend\app.py
```

Terminal PowerShell thu hai:

```powershell
cd frontend
npm run dev
```

Mo `http://localhost:5173`, chon **Device webcam**, bam **Start camera**, sau do
cho phep trinh duyet truy cap webcam.

## Luu y

- Webcam duoc trinh duyet quan ly; backend khong mo camera Windows truc tiep.
- Dang ky va nhan dien deu thuc hien trong giao dien React.
- Neu frontend khong ket noi backend, kiem tra `http://localhost:8000/api/health`.
- Chi tiet backend nam trong [`backend/README.md`](backend/README.md).
