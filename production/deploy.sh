#!/bin/bash

# エラー時に停止
set -e

# 変数設定
APP_NAME="boardapp"
DEPLOY_PATH="/var/www/$APP_NAME"
VENV_PATH="$DEPLOY_PATH/venv"
LOG_PATH="/var/log/$APP_NAME"
NGINX_PATH="/etc/nginx"

# スーパーユーザー権限の確認
if [ "$EUID" -ne 0 ]; then
    echo "このスクリプトはroot権限で実行する必要があります。"
    echo "sudo ./deploy.sh を実行してください。"
    exit 1
fi

# 必要なパッケージのインストール
apt-get update
apt-get install -y python3-venv python3-pip nginx

# アプリケーションユーザーの作成
useradd -r -s /bin/false $APP_NAME || echo "ユーザーは既に存在します"

# ディレクトリ構造の作成
mkdir -p $DEPLOY_PATH/{app,instance,logs,ssl}
mkdir -p $LOG_PATH

# 所有者の設定
chown -R $APP_NAME:$APP_NAME $DEPLOY_PATH
chown -R $APP_NAME:$APP_NAME $LOG_PATH

# Python仮想環境の作成
python3 -m venv $VENV_PATH
source $VENV_PATH/bin/activate

# 依存関係のインストール
pip install --upgrade pip
pip install -r requirements.txt

# アプリケーションファイルのコピー
cp -r ../venv/templates $DEPLOY_PATH/
cp ../venv/boardapp.py $DEPLOY_PATH/app/
cp wsgi.py $DEPLOY_PATH/
cp config.py $DEPLOY_PATH/

# 環境変数の設定
cat > $DEPLOY_PATH/.env << EOL
FLASK_ENV=production
FLASK_APP=boardapp.py
SECRET_KEY=$(python3 -c 'import os; print(os.urandom(24).hex())')
DATABASE_URL=sqlite:///instance/board.db
EOL

# 環境変数ファイルの権限設定
chmod 600 $DEPLOY_PATH/.env
chown $APP_NAME:$APP_NAME $DEPLOY_PATH/.env

# systemdサービスの設定
cat > /etc/systemd/system/$APP_NAME.service << EOL
[Unit]
Description=Gunicorn instance to serve $APP_NAME
After=network.target

[Service]
User=$APP_NAME
Group=$APP_NAME
WorkingDirectory=$DEPLOY_PATH
Environment="PATH=$VENV_PATH/bin"
EnvironmentFile=$DEPLOY_PATH/.env
ExecStart=$VENV_PATH/bin/gunicorn --workers 4 --bind 127.0.0.1:3000 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Nginxの設定
cat > $NGINX_PATH/sites-available/$APP_NAME << EOL
server {
    listen 80;
    server_name \$host;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name \$host;

    ssl_certificate $DEPLOY_PATH/ssl/certificate.crt;
    ssl_certificate_key $DEPLOY_PATH/ssl/private.key;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    access_log $LOG_PATH/access.log;
    error_log $LOG_PATH/error.log;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $DEPLOY_PATH/app/static;
        expires 1y;
        add_header Cache-Control "public, no-transform";
    }

    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
EOL

# Nginxの設定を有効化
ln -sf $NGINX_PATH/sites-available/$APP_NAME $NGINX_PATH/sites-enabled/
rm -f $NGINX_PATH/sites-enabled/default

# SSL証明書のセットアップ
./setup_ssl.sh

# データベースの初期化
source $VENV_PATH/bin/activate
cd $DEPLOY_PATH
FLASK_APP=app/boardapp.py flask db upgrade

# サービスの再起動
systemctl daemon-reload
systemctl enable $APP_NAME
systemctl restart $APP_NAME
systemctl restart nginx

echo "デプロイが完了しました。
アプリケーションは https://\$host で実行されています。" 