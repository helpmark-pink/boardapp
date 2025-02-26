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
    print(f"Current directory: {current_dir}")
    print(f"Python path: {sys.path}")
    sys.exit(1)

# 本番環境の設定を適用
try:
    app.config.from_object('config.ProductionConfig')
except Exception as e:
    print(f"Config error: {e}")
    # デフォルト設定を使用
    pass

# データベース接続の初期化
def init_db(max_retries=3):
    for attempt in range(max_retries):
        try:
            with app.app_context():
                # 接続テスト
                db.engine.connect().execute("SELECT 1")
                return True
        except Exception as e:
            print(f"Database connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    return False

# アプリケーション初期化（Gunicornのプリロード時に実行）
def on_starting(server):
    try:
        init_db()
        print("Database connection initialized successfully")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        sys.exit(1)

# アプリケーションの実行
if __name__ == "__main__":
    app.run()