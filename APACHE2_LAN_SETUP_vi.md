# Deploy Daikai Robot Hub on Raspberry Pi and Access It from Other LAN Devices

This guide explains how to deploy **both the backend and frontend on a
Raspberry Pi**, then access the application from:

- the Raspberry Pi itself;
- another laptop on the same `10.0.0.xxx` network;
- other devices on the same LAN when allowed.

The target setup is:

```text
Laptop / Pi / other devices
           |
           v
http://10.0.0.242
           |
           v
Apache2 on Raspberry Pi
   |                    |
   |                    +-> built React frontend
   |
   +-> /api/* -> FastAPI on 127.0.0.1:8000
```

With this layout:

- the backend runs only on the Pi;
- the frontend is also served by the Pi;
- other laptops only need a browser pointed at the Pi IP;
- you do not need to open port `5173` for Vite;
- you do not need to expose backend port `8000` directly to the LAN.

The examples below assume the Raspberry Pi IP is `10.0.0.242`. Replace it with
the actual Pi IP if yours is different.

## 1. Confirm the Pi and laptop are on the same network

On the Raspberry Pi:

```bash
hostname -I
ip addr
```

You should see an address in the `10.0.0.xxx` range, for example:

```text
10.0.0.242
```

On a Windows laptop, you can check with:

```powershell
ipconfig
ping 10.0.0.242
```

If `ping` fails, common causes are:

- the Pi and laptop are not on the same Wi-Fi or LAN;
- the router has AP isolation or client isolation enabled;
- a firewall is blocking the traffic;
- the Pi IP address has changed.

Recommended:

- configure a DHCP reservation on the router so the Pi keeps a stable IP such
  as `10.0.0.242`;
- if available, you can also use a local hostname such as `facelens-pi.local`,
  but IP is usually the most reliable way to test first.

## 2. Install Apache2 on the Pi

```bash
sudo apt update
sudo apt install -y apache2
sudo a2enmod proxy proxy_http rewrite headers
sudo systemctl enable --now apache2
sudo systemctl status apache2 --no-pager
```

If Apache shows `active (running)`, that part is ready.

## 3. Install dependencies and build the frontend on the Pi

The frontend is built once, then Apache serves the static files from `dist/`.

```bash
cd /home/r1-edu/Documents/Facial-Reconigtion/frontend
npm install
VITE_API_URL="http://10.0.0.242" npm run build
```

After the build completes, copy the frontend files into the Apache web root:

```bash
sudo install -d -m 0755 /var/www/facelens
sudo cp -a dist/. /var/www/facelens/
```

Important notes:

- in the current code, `VITE_API_URL` is embedded into the frontend at build
  time;
- if the Pi IP changes from `10.0.0.242` to something else, rebuild the
  frontend;
- when opened from a laptop, the frontend still calls the API using the
  address baked into the build.

## 4. Configure Apache as a reverse proxy on the Pi

Create the config file:

```bash
sudo nano /etc/apache2/sites-available/facelens.conf
```

Suggested content:

```apache
<VirtualHost *:80>
    ServerName 10.0.0.242
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

Enable the site:

```bash
sudo a2dissite 000-default.conf
sudo a2ensite facelens.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

`sudo apache2ctl configtest` should report:

```text
Syntax OK
```

## 5. Start the FastAPI backend on the Pi

There are two common cases.

### Option A: Use Unitree SDK2 and the robot camera

```bash
source ~/unitree_sdk2_python/.venv/bin/activate

export CYCLONEDDS_HOME="$HOME/cyclonedds/install"
export CMAKE_PREFIX_PATH="$CYCLONEDDS_HOME:$CMAKE_PREFIX_PATH"
export LD_LIBRARY_PATH="$CYCLONEDDS_HOME/lib:$LD_LIBRARY_PATH"
export UNITREE_NETWORK_INTERFACE=eth0

cd ~/Facial-Reconigtion
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

If you prefer to use the project launcher that accepts the robot interface as a
positional argument, this also works:

```bash
cd ~/Facial-Reconigtion
python3 backend eth0 --host 127.0.0.1 --port 8000
```

### Option B: Use only a normal webcam and no Unitree connection

```bash
cd /home/r1-edu/Documents/Facial-Reconigtion
source .venv/bin/activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Important notes:

- the backend should bind to `127.0.0.1` because Apache proxies to it locally;
- laptops on the LAN should **not** access `http://10.0.0.242:8000` directly;
- laptops should open only `http://10.0.0.242`;
- you do not need `npm run dev` on the Pi or laptop after deploying with
  Apache.

## 6. Start the backend automatically after reboot

If you want the backend to be available right after a Pi reboot, create a
`systemd` service. For example:

```bash
sudo nano /etc/systemd/system/facelens-backend.service
```

Example service file for the project `.venv` case:

```ini
[Unit]
Description=Daikai Robot Hub FastAPI backend
After=network.target

[Service]
User=r1-edu
WorkingDirectory=/home/r1-edu/Documents/Facial-Reconigtion
Environment="PATH=/home/r1-edu/Documents/Facial-Reconigtion/.venv/bin"
ExecStart=/home/r1-edu/Documents/Facial-Reconigtion/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now facelens-backend
sudo systemctl status facelens-backend --no-pager
```

If you use the Unitree SDK2 environment instead, update `Environment=` and
`ExecStart=` to match that environment path.

## 7. Open the firewall if needed

If the Pi uses UFW:

```bash
sudo ufw allow 80/tcp
sudo ufw status
```

Only port `80` needs to be opened. Backend port `8000` does not need to be
opened to the LAN.

## 8. Test each layer on the Pi

### Test the backend directly

```bash
curl http://127.0.0.1:8000/api/health
```

### Test Apache proxying to the backend

```bash
curl http://127.0.0.1/api/health
curl -I http://127.0.0.1/
```

### Test from a laptop on the same LAN

On the Windows laptop:

```powershell
ping 10.0.0.242
```

Then open the browser at:

```text
http://10.0.0.242
```

If you want a quick command-line test from the laptop:

```powershell
curl http://10.0.0.242/api/health
```

If that returns the health JSON, the laptop can reach the backend through
Apache on the Pi.

## 9. Expected LAN usage flow

After deployment:

1. The backend runs on the Pi.
2. Apache runs on the Pi.
3. The built frontend lives in `/var/www/facelens`.
4. Another laptop only needs to open `http://10.0.0.242`.
5. Every `/api/...` request is forwarded by Apache to the backend at
   `127.0.0.1:8000`.

In short:

- the Pi is the server;
- the other laptop is the client;
- any device on the same `10.0.0.xxx` network can access it when allowed.

## 10. Webcam notes for another laptop

If you open the site from another laptop using:

```text
http://10.0.0.242
```

the browser will often **not allow** `getUserMedia()` access to the laptop's
local webcam, because this is not a secure context. That means:

- file upload mode still works;
- the Unitree robot stream still works;
- the laptop's local webcam may be blocked if you use plain HTTP only.

If you want another laptop to use its **local browser webcam**, switch Apache
to HTTPS and use a certificate trusted by that laptop.

## 11. Update the frontend after code changes

Whenever you change frontend code, rebuild and copy it again:

```bash
cd /home/r1-edu/Documents/Facial-Reconigtion/frontend
VITE_API_URL="http://10.0.0.242" npm run build
sudo cp -a dist/. /var/www/facelens/
sudo systemctl reload apache2
```

If the Pi IP changes, remember to update `VITE_API_URL`.

## 12. Troubleshooting

### A laptop cannot open `http://10.0.0.242`

On the Pi:

```bash
hostname -I
sudo systemctl status apache2 --no-pager
sudo ss -ltnp | grep ':80'
```

Also check:

- whether the Pi is really using IP `10.0.0.242`;
- whether the Pi and laptop are on the same subnet;
- whether the router has client isolation enabled;
- whether UFW or another firewall is blocking port 80.

### Apache returns `503 Service Unavailable`

This usually means the backend is not running:

```bash
curl http://127.0.0.1:8000/api/health
sudo systemctl status facelens-backend --no-pager
```

If you are not using `systemd`, check the terminal where `uvicorn` should be
running.

### The frontend loads but API requests fail

This usually means the frontend was built with the wrong IP:

```bash
cd /home/r1-edu/Documents/Facial-Reconigtion/frontend
VITE_API_URL="http://10.0.0.242" npm run build
sudo cp -a dist/. /var/www/facelens/
sudo systemctl reload apache2
```

Also inspect the Apache log:

```bash
sudo tail -f /var/log/apache2/facelens-error.log
```

### Refreshing a child route returns `404`

Check that `rewrite` is enabled:

```bash
sudo a2enmod rewrite
sudo a2ensite facelens.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

### The home page loads but another laptop cannot use its webcam

This is a normal HTTP limitation on LAN access. Your options are:

- use image upload instead of browser webcam;
- use the Unitree camera stream through the backend;
- or configure HTTPS in Apache with a certificate trusted by the laptop.
