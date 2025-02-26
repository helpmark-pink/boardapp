#!/bin/bash

# エラー時に停止
set -e

# 変数設定
SSL_DIR="/Users/$USER/Applications/boardapp/ssl"
mkdir -p $SSL_DIR

# 自己署名証明書の生成
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout $SSL_DIR/private.key \
    -out $SSL_DIR/certificate.crt \
    -subj "/C=JP/ST=Tokyo/L=Tokyo/O=Development/CN=localhost"

chmod 600 $SSL_DIR/private.key
chmod 644 $SSL_DIR/certificate.crt

echo "SSL証明書のセットアップが完了しました。
証明書は $SSL_DIR に保存されています。" 