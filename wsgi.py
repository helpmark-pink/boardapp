import sys
import os
import time
from sqlalchemy.exc import OperationalError

# アプリケーションのパスを追加
current_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, current_dir)

try:
    from boardapp import app, db
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# 本番環境の設定を適用
try:
    app.config.from_object('config.ProductionConfig')
except Exception as e:
    print(f"Config error: {e}")
    # デフォルト設定を使用
    pass

# データベースの初期化（リトライ付き）
def init_db(max_retries=5):
    for attempt in range(max_retries):
        try:
            with app.app_context():
                db.create_all()
            print("Database tables created successfully")
            return True
        except OperationalError as e:
            print(f"Database initialization attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数バックオフ
                continue
            raise
    return False

# アプリケーション初期化
if __name__ != "__main__":
    try:
        init_db()
        print("Database initialization successful")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        # エラーをログに記録するが、アプリケーションは続行
        pass

# アプリケーションの実行
if __name__ == "__main__":
    app.run()