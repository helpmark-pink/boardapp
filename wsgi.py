import sys
import os
import time
from sqlalchemy.exc import OperationalError

# アプリケーションのパスを追加
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from boardapp import app, db

# 本番環境の設定を適用
app.config.from_object('config.ProductionConfig')

# データベースの初期化（リトライ付き）
def init_db(max_retries=5):
    for attempt in range(max_retries):
        try:
            with app.app_context():
                db.create_all()
            return True
        except OperationalError:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数バックオフ
                continue
            raise
    return False

# データベース初期化の実行
init_db()

if __name__ == "__main__":
    app.run() 