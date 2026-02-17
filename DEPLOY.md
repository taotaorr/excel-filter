# 阿里云服务器部署指南

## 环境要求
- Ubuntu 20.04+ / CentOS 7+ / Windows Server
- Python 3.8+

---

## 方式一：Linux 服务器部署（推荐）

### 1. 连接服务器
```bash
ssh root@你的服务器IP
```

### 2. 安装 Python 和依赖
```bash
# Ubuntu/Debian
apt update
apt install -y python3 python3-pip python3-venv

# CentOS
yum install -y python3 python3-pip
```

### 3. 创建项目目录
```bash
mkdir -p /var/www/excel-filter
cd /var/www/excel-filter
```

### 4. 上传项目文件
可以通过以下方式上传：
- Git: `git clone 你的仓库地址`
- FTP/SFTP: 使用 FileZilla 等工具上传

### 5. 创建虚拟环境并安装依赖
```bash
python3 -m venv venv
source venv/bin/activate
pip install flask pandas openpyxl gunicorn
```

### 6. 配置防火墙（如果需要）
```bash
# 开放 5000 端口
ufw allow 5000  # Ubuntu
# 或
firewall-cmd --permanent --add-port=5000/tcp  # CentOS
```

### 7. 测试运行
```bash
python3 app.py
```
访问 `http://你的服务器IP:5000` 测试

### 8. 使用 Gunicorn 后台运行（生产环境）
```bash
# 安装 gunicorn (已在上面安装)
# 创建启动脚本
cat > /etc/systemd/system/excel-filter.service << EOF
[Unit]
Description=Excel Filter App
After=network.target

[Service]
User=root
WorkingDirectory=/var/www/excel-filter
Environment="PATH=/var/www/excel-filter/venv/bin"
ExecStart=/var/www/excel-filter/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
systemctl daemon-reload
systemctl enable excel-filter
systemctl start excel-filter
```

### 9. 配置 Nginx（可选，反向代理）
```bash
apt install -y nginx

cat > /etc/nginx/sites-available/excel-filter << EOF
server {
    listen 80;
    server_name 你的域名或IP;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

ln -s /etc/nginx/sites-available/excel-filter /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```
然后访问 `http://你的服务器IP` 或 `http://你的域名`

---

## 方式二：Windows Server 部署

### 1. 安装 Python
从 https://www.python.org/downloads/ 下载并安装 Python 3.8+

### 2. 安装依赖
打开 PowerShell：
```powershell
pip install flask pandas openpyxl gunicorn
```

### 3. 运行应用
```powershell
python app.py
```

### 4. 配置防火墙
在 Windows 防火墙中开放 5000 端口

### 5. 后台运行（使用 NSSM）
下载 NSSM: https://nssm.cc/download

```powershell
nssm install ExcelFilter "C:\Python39\python.exe" "C:\你的项目路径\app.py"
nssm set ExcelFilter AppDirectory "C:\你的项目路径"
nssm start ExcelFilter
```

---

## 阿里云安全组配置

在阿里云控制台中：
1. 进入 ECS 实例 → 安全组 → 配置规则
2. 添加入方向规则：
   - 协议：TCP
   - 端口：5000（或 80 如果用 Nginx）
   - 来源：0.0.0.0/0

---

## 常见问题

### 1. 上传文件太大
修改 `app.py` 中的 `app.config['MAX_CONTENT_LENGTH']` 值

### 2. 中文显示乱码
确保 Excel 文件编码为 UTF-8，或在读取时指定编码

### 3. 端口被占用
```bash
# 查看端口占用
lsof -i:5000
# 杀掉进程
kill -9 <PID>
```
