# Deploy Daikai Robot Hub with Apache2 and Access It from Other LAN Devices

This guide explains how to deploy **both the backend and frontend on an Ubuntu
computer**, then access the application from:

- the Ubuntu computer itself;
- another laptop on the same LAN;
- other devices on the same LAN when allowed.

The target setup is:

```text
Laptop / Ubuntu server / other devices
           |
           v
http://192.168.0.75
           |
           v
Apache2 on the Ubuntu server
   |                    |
   |                    +-> built React frontend
   |
   +-> /api/* -> FastAPI on 127.0.0.1:8000
```

With this layout:

- the backend runs only on the Ubuntu server;
- Apache serves `frontend/dist` directly from the project directory;
- other laptops only need a browser pointed at the server IP;
- you do not need to open port `5173` for Vite;
- you do not need to expose backend port `8000` directly to the LAN.

The examples below assume:

- project directory: `/home/unitree/Daikai_Robot_Hub`;
- server IP: `192.168.0.75`;
- Linux user: `unitree`.

Replace these values if they are different on your computer.

## 1. Confirm the server and laptop are on the same network

On the Ubuntu server:

```bash
hostname -I
ip addr
```

You should see the server address, for example:

```text
192.168.0.75
```

On a Windows laptop, you can check with:

```powershell
ipconfig
ping 192.168.0.75
```

If `ping` fails, common causes are:

- the server and laptop are not on the same Wi-Fi or LAN;
- the router has AP isolation or client isolation enabled;
- a firewall is blocking the traffic;
- the server IP address has changed.

Recommended:

- configure a DHCP reservation on the router so the server keeps a stable IP
  such as `192.168.0.75`;
- if available, you can also use a local hostname such as `daikai-robot.local`,
  but IP is usually the most reliable way to test first.

## 2. Install Apache2 and enable the required modules

```bash
sudo apt update
sudo apt install -y apache2 acl
sudo a2enmod proxy proxy_http rewrite headers
sudo systemctl enable --now apache2
sudo systemctl status apache2 --no-pager
```

Confirm that the required modules are loaded:

```bash
sudo apache2ctl -M | grep -E 'proxy_module|proxy_http_module|rewrite_module|headers_module'
```

If Apache reports `Invalid command 'ProxyRequests'`, `mod_proxy` is not loaded.
Run `sudo a2enmod proxy proxy_http`, then repeat `apache2ctl configtest`.

## 3. Install dependencies and build the frontend

The frontend is built once, then Apache serves the static files from `dist/`.

```bash
cd ~/Daikai_Robot_Hub/frontend
npm install
VITE_API_URL="http://192.168.0.75" npm run build
```

Apache serves `frontend/dist` directly. Do not copy the build to `/var/www`.
Confirm that the build exists:

```bash
test -f /home/unitree/Daikai_Robot_Hub/frontend/dist/index.html && echo "Frontend build OK"
```

Apache runs as `www-data`. Grant that user read/traverse access only to the
required paths, without changing ownership of the project:

```bash
sudo setfacl -m u:www-data:x /home/unitree
sudo setfacl -m u:www-data:x /home/unitree/Daikai_Robot_Hub
sudo setfacl -m u:www-data:x /home/unitree/Daikai_Robot_Hub/frontend
sudo setfacl -R -m u:www-data:rX /home/unitree/Daikai_Robot_Hub/frontend/dist
```

Verify Apache can read the built entry point:

```bash
sudo -u www-data test -r /home/unitree/Daikai_Robot_Hub/frontend/dist/index.html \
  && echo "Apache can read index.html"
```

Important notes:

- in the current code, `VITE_API_URL` is embedded into the frontend at build
  time;
- if the server IP changes from `192.168.0.75` to something else, rebuild the
  frontend;
- when opened from a laptop, the frontend still calls the API using the
  address baked into the build.

## 4. Configure Apache as a reverse proxy

Create the config file:

```bash
sudo nano /etc/apache2/sites-available/Daikai_Robot_Hub.conf
```

Suggested content:

```apache
<VirtualHost *:80>
    ServerName 192.168.0.75
    DocumentRoot /home/unitree/Daikai_Robot_Hub/frontend/dist

    ProxyRequests Off
    ProxyPreserveHost On
    ProxyTimeout 600

    ProxyPass        /api/ http://127.0.0.1:8000/api/
    ProxyPassReverse /api/ http://127.0.0.1:8000/api/

    <Directory /home/unitree/Daikai_Robot_Hub/frontend/dist>
        Options -Indexes +FollowSymLinks
        AllowOverride None
        Require all granted

        RewriteEngine On
        RewriteCond %{REQUEST_FILENAME} -f [OR]
        RewriteCond %{REQUEST_FILENAME} -d
        RewriteRule ^ - [L]
        RewriteRule . /index.html [L]
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/daikai-robot-hub-error.log
    CustomLog ${APACHE_LOG_DIR}/daikai-robot-hub-access.log combined
</VirtualHost>
```

Enable the site:

```bash
sudo a2dissite 000-default.conf
sudo a2ensite Daikai_Robot_Hub.conf
sudo a2enmod proxy proxy_http rewrite headers
sudo apache2ctl configtest
sudo systemctl reload apache2
```

`sudo apache2ctl configtest` should report:

```text
Syntax OK
```

## 5. Start the FastAPI backend

There are two common cases.

### Option A: Use Unitree SDK2 and the robot camera

```bash
source ~/Daikai_Robot_Hub/.venv/bin/activate

export CYCLONEDDS_HOME="$HOME/cyclonedds/install"
export CMAKE_PREFIX_PATH="$CYCLONEDDS_HOME:$CMAKE_PREFIX_PATH"
export LD_LIBRARY_PATH="$CYCLONEDDS_HOME/lib:$LD_LIBRARY_PATH"
export UNITREE_NETWORK_INTERFACE=eth0

cd ~/Daikai_Robot_Hub
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

If you prefer to use the project launcher that accepts the robot interface as a
positional argument, this also works:

```bash
cd ~/Daikai_Robot_Hub
python -m backend eth0 --host 127.0.0.1 --port 8000
```

### Option B: Use only a normal webcam and no Unitree connection

```bash
cd ~/Daikai_Robot_Hub
source .venv/bin/activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Important notes:

- the backend should bind to `127.0.0.1` because Apache proxies to it locally;
- laptops on the LAN should **not** access `http://192.168.0.75:8000` directly;
- laptops should open only `http://192.168.0.75`;
- you do not need `npm run dev` on the server or laptop after deploying with
  Apache.

## 6. Start the backend automatically after reboot

Use a `systemd` service to start the backend automatically after a reboot and
restart it if the process fails.

### 6.1. Verify the runtime environment

Find the network interface connected to the Unitree robot:

```bash
ip -br link
```

The examples below use `eth0`. Replace it with the actual interface, such as
`enp2s0`, if necessary.

Before creating the service, confirm that the project virtual environment has
both the backend dependencies and Unitree SDK:

```bash
cd ~/Daikai_Robot_Hub
source .venv/bin/activate

python --version
python -m pip --version
python -c "import fastapi, cv2; print('Backend dependencies OK')"
python -c "from unitree_sdk2py.go2.video.video_client import VideoClient; print('Unitree SDK OK')"
```

Do not continue until both import checks succeed. The service must use the same
Python environment in which `unitree_sdk2py` is installed.

### 6.2. Create the service

```bash
sudo nano /etc/systemd/system/daikai-robot-hub-backend.service
```

Add this content:

```ini
[Unit]
Description=Daikai Robot Hub FastAPI Backend
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=unitree
Group=unitree
WorkingDirectory=/home/unitree/Daikai_Robot_Hub

Environment="HOME=/home/unitree"
Environment="PATH=/home/unitree/Daikai_Robot_Hub/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
Environment="CYCLONEDDS_HOME=/home/unitree/cyclonedds/install"
Environment="LD_LIBRARY_PATH=/home/unitree/cyclonedds/install/lib"
Environment="UNITREE_NETWORK_INTERFACE=eth0"
Environment="PYTHONUNBUFFERED=1"

ExecStart=/home/unitree/Daikai_Robot_Hub/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1

Restart=on-failure
RestartSec=3
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

Keep `--workers 1`. The Unitree DDS clients are shared resources and should not
be initialized by multiple Uvicorn workers.

### 6.3. Validate and start the service

Validate the service file before enabling it:

```bash
sudo systemd-analyze verify /etc/systemd/system/daikai-robot-hub-backend.service
sudo systemctl daemon-reload
sudo systemctl enable --now daikai-robot-hub-backend
sudo systemctl status daikai-robot-hub-backend --no-pager
```

Test the backend directly and through Apache:

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1/api/health
```

### 6.4. Inspect logs and deploy backend updates

Show recent service logs:

```bash
sudo journalctl -u daikai-robot-hub-backend -n 100 --no-pager
```

Follow logs in real time:

```bash
sudo journalctl -fu daikai-robot-hub-backend
```

After changing backend code or configuration, restart and verify the service:

```bash
sudo systemctl restart daikai-robot-hub-backend
sudo systemctl status daikai-robot-hub-backend --no-pager
```

If the Unitree SDK or virtual environment is stored elsewhere, update `PATH`
and `ExecStart` to use that environment. Also update `CYCLONEDDS_HOME`,
`LD_LIBRARY_PATH`, and `UNITREE_NETWORK_INTERFACE` when their actual values are
different from the example.

## 7. Open the firewall if needed

If the server uses UFW:

```bash
sudo ufw allow 80/tcp
sudo ufw status
```

Only port `80` needs to be opened. Backend port `8000` does not need to be
opened to the LAN.

## 8. Test each layer on the server

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
ping 192.168.0.75
```

Then open the browser at:

```text
http://192.168.0.75
```

If you want a quick command-line test from the laptop:

```powershell
curl http://192.168.0.75/api/health
```

If that returns the health JSON, the laptop can reach the backend through
Apache on the server.

## 9. Expected LAN usage flow

After deployment:

1. The backend runs on the Ubuntu server.
2. Apache runs on the Ubuntu server.
3. The built frontend stays in `~/Daikai_Robot_Hub/frontend/dist`.
4. Another laptop only needs to open `http://192.168.0.75`.
5. Every `/api/...` request is forwarded by Apache to the backend at
   `127.0.0.1:8000`.

In short:

- the Ubuntu computer is the server;
- the other laptop is the client;
- any device on the same LAN can access it when allowed.

## 10. Webcam notes for another laptop

If you open the site from another laptop using:

```text
http://192.168.0.75
```

the browser will often **not allow** `getUserMedia()` access to the laptop's
local webcam, because this is not a secure context. That means:

- file upload mode still works;
- the Unitree robot stream still works;
- the laptop's local webcam may be blocked if you use plain HTTP only.

If you want another laptop to use its **local browser webcam**, switch Apache
to HTTPS and use a certificate trusted by that laptop.

## 11. Update the frontend after code changes

Whenever you change frontend code, rebuild it in place and refresh Apache's
read access:

```bash
cd ~/Daikai_Robot_Hub/frontend
VITE_API_URL="http://192.168.0.75" npm run build
sudo setfacl -R -m u:www-data:rX /home/unitree/Daikai_Robot_Hub/frontend/dist
sudo systemctl reload apache2
```

If the server IP changes, remember to update `VITE_API_URL`.

## 12. Troubleshooting

### A laptop cannot open `http://192.168.0.75`

On the server:

```bash
hostname -I
sudo systemctl status apache2 --no-pager
sudo ss -ltnp | grep ':80'
```

Also check:

- whether the server is really using IP `192.168.0.75`;
- whether the server and laptop are on the same subnet;
- whether the router has client isolation enabled;
- whether UFW or another firewall is blocking port 80.

### `configtest` reports `Invalid command 'ProxyRequests'`

This means the Apache proxy module is not enabled. Enable both proxy modules,
confirm they are loaded, then test and reload Apache:

```bash
sudo a2enmod proxy proxy_http
sudo apache2ctl -M | grep -E 'proxy_module|proxy_http_module'
sudo apache2ctl configtest
sudo systemctl reload apache2
```

The expected module output contains `proxy_module` and `proxy_http_module`, and
the config test should finish with `Syntax OK`.

### Apache returns `503 Service Unavailable`

This usually means the backend is not running:

```bash
curl http://127.0.0.1:8000/api/health
sudo systemctl status daikai-robot-hub-backend --no-pager
```

If you are not using `systemd`, check the terminal where `uvicorn` should be
running.

### The frontend loads but API requests fail

This usually means the frontend was built with the wrong IP:

```bash
cd ~/Daikai_Robot_Hub/frontend
VITE_API_URL="http://192.168.0.75" npm run build
sudo setfacl -R -m u:www-data:rX /home/unitree/Daikai_Robot_Hub/frontend/dist
sudo systemctl reload apache2
```

Also inspect the Apache log:

```bash
sudo tail -f /var/log/apache2/daikai-robot-hub-error.log
```

### Refreshing a child route returns `404`

Check that `rewrite` is enabled:

```bash
sudo a2enmod rewrite
sudo a2ensite Daikai_Robot_Hub.conf
sudo apache2ctl configtest
sudo systemctl reload apache2
```

### The home page loads but another laptop cannot use its webcam

This is a normal HTTP limitation on LAN access. Your options are:

- use image upload instead of browser webcam;
- use the Unitree camera stream through the backend;
- or configure HTTPS in Apache with a certificate trusted by the laptop.
