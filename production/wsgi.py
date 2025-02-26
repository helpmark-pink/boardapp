import sys
import os

# アプリケーションのパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

from boardapp import app as application

# 本番環境の設定を適用
application.config.from_object('config.ProductionConfig')

# アプリケーションの初期化
if __name__ == "__main__":
    application.run() 