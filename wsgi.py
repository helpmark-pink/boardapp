import sys
import os
import time
from sqlalchemy.exc import OperationalError

# アプリケーションのパスを追加
current_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, current_dir)

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
        except OperationalError as e:
            print(f"Database initialization attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数バックオフ
                continue
            raise
    return False

# データベース初期化の実行
try:
    init_db()
    print("Database initialization successful")
except Exception as e:
    print(f"Database initialization failed: {e}")

if __name__ == "__main__":
    app.run()