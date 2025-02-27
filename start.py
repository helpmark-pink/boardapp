import os
from boardapp import app, db

# データベースディレクトリの作成
if not os.path.exists('instance'):
    os.makedirs('instance')

# 環境変数の設定
os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_APP'] = 'boardapp'

# データベースの初期化
with app.app_context():
    db.create_all()

# アプリケーションの起動
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port) 