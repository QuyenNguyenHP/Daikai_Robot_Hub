# Truy cap FaceLens tu laptop trong cung mang bang Apache2

Tai lieu nay huong dan chay backend va frontend FaceLens tren Raspberry Pi, sau
do truy cap ung dung tu mot laptop trong cung mang LAN/Wi-Fi.

Kien truc sau khi cai dat:

```text
Laptop -> http://IP_CUA_PI:80 -> Apache2 -> frontend React
                                    |
                                    +-> /api/* -> FastAPI 127.0.0.1:8000
```

Apache2 phuc vu frontend da build va reverse proxy `/api/` den backend. Khong
can mo cong `5173` hoac `8000` cho laptop.

## 1. Tim dia chi IP cua Raspberry Pi

Tren Pi, chay:

```bash
hostname -I
```

Vi du Pi co dia chi `192.168.1.50`. Hay thay dia chi nay bang IP thuc te trong
tat ca lenh ben duoi.

Nen dat DHCP reservation tren router de Pi luon nhan cung mot dia chi IP. Pi va
laptop phai ket noi cung mang, va router khong duoc bat AP/client isolation.

## 2. Cai Apache2

```bash
sudo apt update
sudo apt install -y apache2
sudo a2enmod proxy proxy_http rewrite headers
sudo systemctl enable --now apache2
```

Kiem tra Apache:

```bash
sudo systemctl status apache2 --no-pager
```

## 3. Build frontend cho dia chi cua Pi

Vite dua `VITE_API_URL` vao frontend tai thoi diem build. Chay tren Pi:

```bash
cd ~/Facial-Reconigtion/frontend
npm install
VITE_API_URL="http://192.168.18.50" npm run build
```

Thu muc ket qua la `frontend/dist/`. Copy noi dung nay vao thu muc Apache:

```bash
sudo install -d -m 0755 /var/www/facelens
sudo cp -a dist/. /var/www/facelens/
```

Neu IP cua Pi thay doi, can build lai frontend voi `VITE_API_URL` moi va copy
lai thu muc `dist/`.

## 4. Cau hinh Apache2

Tao file cau hinh:

```bash
sudo nano /etc/apache2/sites-available/facelens.conf
```

Dan noi dung sau, thay `192.168.1.50` bang IP cua Pi:

```apache
<VirtualHost *:80>
    ServerName 192.168.1.50
    DocumentRoot /var/www/facelens

    ProxyRequests Off
    ProxyPreserveHost On
    ProxyTimeout 600
    ProxyPass        /api/ http://127.0.0.1:8000/api/
    ProxyPassReverse /api/ http://127.0.0.1:8000/api/

    <Directory /var/www/facelens>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted

        RewriteEngine On
        RewriteCond %{REQUEST_FILENAME} -f [OR]
        RewriteCond %{REQUEST_FILENAME} -d
        RewriteRule ^ - [L]
        RewriteRule . /index.html [L]
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/facelens-error.log
    CustomLog ${APACHE_LOG_DIR}/facelens-access.log combined
</VirtualHost>
```

Kich hoat website va kiem tra cau hinh:

```bash
sudo a2dissite 000-default.conf
sudo a2ensite facelens.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

`apache2ctl configtest` phai tra ve `Syntax OK` truoc khi reload.

## 5. Chay backend tren Pi

Backend va Unitree SDK2 phai dung cung mot Python environment. Neu dung camera
Unitree R1:

```bash
source ~/unitree_sdk2_python/.venv/bin/activate

export CYCLONEDDS_HOME="$HOME/cyclonedds/install"
export CMAKE_PREFIX_PATH="$CYCLONEDDS_HOME:$CMAKE_PREFIX_PATH"
export LD_LIBRARY_PATH="$CYCLONEDDS_HOME/lib:$LD_LIBRARY_PATH"
export UNITREE_NETWORK_INTERFACE=enxa0cec86d95d6

cd /home/r1-edu/Documents/Facial-Reconigtion
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Thay `enxa0cec86d95d6` bang card mang ket noi voi robot. Khong dung nhieu
Uvicorn worker trong che do Unitree.

Neu chi dung webcam va `.venv` cua FaceLens:

```bash
cd /home/r1-edu/Documents/Facial-Reconigtion
source .venv/bin/activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Khong can chay `npm run dev`: Apache dang phuc vu frontend tu
`/var/www/facelens`.

## 6. Mo firewall neu dang dung UFW

Chi mo cong Apache, khong can mo cong backend `8000`:

```bash
sudo ufw allow 80/tcp
sudo ufw status
```

Neu UFW khong duoc cai hoac dang inactive, co the bo qua buoc nay.

## 7. Kiem tra tren Pi

Kiem tra backend truc tiep:

```bash
curl http://127.0.0.1:8000/api/health
```

Kiem tra qua Apache:

```bash
curl http://127.0.0.1/api/health
curl -I http://127.0.0.1/
```

Neu ca ba lenh thanh cong, mo trinh duyet tren laptop va truy cap:

```text
http://192.168.1.50
```

## 8. Luu y ve webcam cua laptop

Che do **Unitree R1 camera**, xem giao dien va upload file co the dung qua HTTP
trong LAN. Tuy nhien, trinh duyet chi cho phep `getUserMedia()` truy cap webcam
trong secure context. `http://localhost` duoc chap nhan, nhung
`http://192.168.1.50` thuong khong duoc chap nhan.

Neu can dung **Device webcam** cua laptop, phai cau hinh HTTPS tren Apache voi
chung chi duoc laptop tin cay. Chung chi self-signed ma trinh duyet chua trust
van co the lam webcam bi chan. Khi chuyen sang HTTPS, build lai frontend bang
URL HTTPS:

```bash
cd /home/r1-edu/Documents/Facial-Reconigtion/frontend
VITE_API_URL="https://TEN_MIEN_HOAC_HOSTNAME" npm run build
sudo cp -a dist/. /var/www/facelens/
```

## 9. Cap nhat frontend sau khi sua code

```bash
cd /home/r1-edu/Documents/Facial-Reconigtion/frontend
VITE_API_URL="http://192.168.1.50" npm run build
sudo cp -a dist/. /var/www/facelens/
sudo systemctl reload apache2
```

## Xu ly loi

### Laptop khong mo duoc website

```bash
hostname -I
sudo systemctl status apache2 --no-pager
sudo ss -ltnp | grep ':80'
```

Kiem tra laptop va Pi cung subnet, firewall cho phep TCP 80, va router khong bat
client isolation.

### Apache tra ve `503 Service Unavailable`

Backend chua chay hoac khong lang nghe tai `127.0.0.1:8000`:

```bash
curl http://127.0.0.1:8000/api/health
```

### Trang hien ra nhung API loi

Kiem tra frontend da duoc build bang dung IP cua Pi:

```bash
cd /home/r1-edu/Documents/Facial-Reconigtion/frontend
VITE_API_URL="http://192.168.1.50" npm run build
sudo cp -a dist/. /var/www/facelens/
```

Xem log Apache va backend:

```bash
sudo tail -f /var/log/apache2/facelens-error.log
```

### Refresh trang con bi loi `404`

Kiem tra module rewrite va site da duoc kich hoat:

```bash
sudo a2enmod rewrite
sudo a2ensite facelens.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```
