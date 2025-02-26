#!/bin/bash

# エラー時に停止
set -e

# 環境変数ファイルの作成
cat > /var/www/boardapp/.env << EOL
FLASK_ENV=production
FLASK_APP=boardapp.py
SECRET_KEY=$(python3 -c 'import os; print(os.urandom(24).hex())')
DATABASE_URL=sqlite:///instance/board.db
EOL

# 環境変数ファイルのパーミッション設定
chmod 600 /var/www/boardapp/.env

# データベースバックアップディレクトリの作成
BACKUP_DIR="/var/www/boardapp/backups"
mkdir -p $BACKUP_DIR
chmod 700 $BACKUP_DIR

# データベースバックアップスクリプトの作成
cat > /var/www/boardapp/backup_db.sh << EOL
#!/bin/bash

# バックアップファイル名の設定
BACKUP_FILE="\${BACKUP_DIR}/board_\$(date +%Y%m%d_%H%M%S).db"

# データベースのバックアップ
cp /var/www/boardapp/instance/board.db "\$BACKUP_FILE"

# 30日以上前のバックアップを削除
find "\$BACKUP_DIR" -name "board_*.db" -type f -mtime +30 -delete

echo "データベースのバックアップが完了しました: \$BACKUP_FILE"
EOL

# バックアップスクリプトの実行権限を設定
chmod +x /var/www/boardapp/backup_db.sh

# cronジョブの設定（毎日午前3時にバックアップを実行）
(crontab -l 2>/dev/null; echo "0 3 * * * /var/www/boardapp/backup_db.sh") | crontab -

echo "本番環境のセットアップが完了しました。" 