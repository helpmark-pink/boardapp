import sys
import os

# アプリケーションのパスを追加
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from boardapp import app, db

# 本番環境の設定を適用
app.config.from_object('config.ProductionConfig')

# データベースの初期化
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run() 