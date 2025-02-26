from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
from sqlalchemy.exc import OperationalError, DatabaseError
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

app = Flask(__name__, template_folder='templates')

# 環境設定
ENV = os.getenv('FLASK_ENV', 'development')
DEBUG = ENV == 'development'

# データベースURL設定
database_url = os.getenv('DATABASE_URL', 'sqlite:///board.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
    if 'sslmode=' not in database_url:
        database_url += '?sslmode=require'
elif database_url.startswith('postgresql://') and 'sslmode=' not in database_url:
    database_url += '?sslmode=require'

# データベース設定
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,  # デフォルトのコネクションプールサイズ
    'max_overflow': 10,  # プールサイズを超えて作成可能な追加コネクション数
    'pool_timeout': 30,  # プールからコネクションを取得する際のタイムアウト（秒）
    'pool_recycle': 1800,  # コネクションを再利用する時間（秒）
    'pool_pre_ping': True,  # コネクション使用前の生存確認
    'connect_args': {
        'connect_timeout': 10,  # データベース接続タイムアウト（秒）
        'keepalives': 1,  # TCP keepaliveを有効化
        'keepalives_idle': 30,  # アイドル状態でのkeepaliveまでの時間（秒）
        'keepalives_interval': 10,  # keepaliveの間隔（秒）
        'keepalives_count': 5  # keepaliveの再試行回数
    }
}

# セッション設定
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_SECURE'] = ENV != 'development'  # 本番環境ではTrue
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# レート制限の設定
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# CSRFプロテクション
csrf = CSRFProtect(app)
db = SQLAlchemy(app)

# データベース接続リトライデコレータ
def retry_on_db_error(max_retries=3, delay=1):
    def decorator(f):
        from functools import wraps
        import time
        
        @wraps(f)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return f(*args, **kwargs)
                except (OperationalError, DatabaseError) as e:
                    retries += 1
                    if retries == max_retries:
                        app.logger.error(f"最大リトライ回数に達しました: {str(e)}")
                        raise
                    app.logger.warning(f"データベースエラー、リトライ {retries}/{max_retries}: {str(e)}")
                    time.sleep(delay * retries)  # 指数バックオフ
            return f(*args, **kwargs)
        return wrapper
    return decorator

# モデル定義
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

class Thread(db.Model):
    thread_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    posts = db.relationship('Post', backref='thread', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('thread.thread_id'), nullable=False)
    post_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.now)
    rep_id = db.Column(db.Integer, nullable=True)

# セキュリティヘッダー設定
@app.after_request
def add_security_headers(response):
    # Content Security Policy
    csp = {
        'default-src': "'self'",
        'script-src': "'self'",
        'style-src': "'self' 'unsafe-inline'",
        'img-src': "'self' data:",
        'font-src': "'self'",
        'frame-ancestors': "'none'"
    }
    response.headers['Content-Security-Policy'] = '; '.join(f"{key} {value}" for key, value in csp.items())
    
    # その他のセキュリティヘッダー
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    return response

# CSRF エラーハンドラー
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template('error.html', message='CSRF token has expired or is invalid'), 400

@app.errorhandler(OperationalError)
def handle_db_operational_error(e):
    app.logger.error(f"Database operational error: {str(e)}")
    return render_template('error.html', message='データベース接続エラーが発生しました。しばらく経ってから再度お試しください。'), 500

@app.errorhandler(DatabaseError)
def handle_db_error(e):
    app.logger.error(f"Database error: {str(e)}")
    return render_template('error.html', message='データベースエラーが発生しました。'), 500

# レート制限をルートに適用
@limiter.limit("5 per minute")
@app.route("/", methods=["GET", "POST"])
@retry_on_db_error(max_retries=3, delay=1)
def top():
    if request.method == "POST":
        thread_title = request.form.get("thread-title")
        if thread_title:
            try:
                new_thread = Thread(title=thread_title)
                db.session.add(new_thread)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"スレッド作成エラー: {str(e)}")
                raise
            return redirect(url_for("top"))
    
    threads = Thread.query.order_by(Thread.created_at.desc()).all()
    return render_template("threads.html", threads_fetches=threads)

@limiter.limit("20 per minute")
@app.route("/<int:thread_id>", methods=["GET", "POST"])
@retry_on_db_error(max_retries=3, delay=1)
def posts(thread_id):
    thread = Thread.query.get_or_404(thread_id)
    
    if request.method == "POST":
        name = request.form.get("post-name")
        message = request.form.get("post-message")
        
        if name and message:
            try:
                post_id = Post.query.filter_by(thread_id=thread_id).count() + 1
                new_post = Post(
                    thread_id=thread_id,
                    post_id=post_id,
                    name=name,
                    message=message
                )
                db.session.add(new_post)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"投稿作成エラー: {str(e)}")
                raise
            return redirect(url_for("posts", thread_id=thread_id))
    
    posts = Post.query.filter_by(thread_id=thread_id).order_by(Post.date.asc()).all()
    return render_template("posts.html", thread_title=thread.title, posts_fetches=posts, thread_id=thread_id)

@limiter.limit("10 per minute")
@app.route("/<int:thread_id>/replyto-<int:replyto_id>", methods=["GET", "POST"])
@retry_on_db_error(max_retries=3, delay=1)
def reply(thread_id, replyto_id):
    thread = Thread.query.get_or_404(thread_id)
    original_post = Post.query.filter_by(thread_id=thread_id, post_id=replyto_id).first_or_404()
    
    if request.method == "POST":
        name = request.form.get("post-name")
        message = request.form.get("post-message")
        
        if name and message:
            try:
                post_id = Post.query.filter_by(thread_id=thread_id).count() + 1
                new_reply = Post(
                    thread_id=thread_id,
                    post_id=post_id,
                    name=name,
                    message=message,
                    rep_id=replyto_id
                )
                db.session.add(new_reply)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"返信作成エラー: {str(e)}")
                raise
            return redirect(url_for("posts", thread_id=thread_id))
    
    return render_template("reply.html", 
                         thread_title=thread.title, 
                         posts_fetches=[original_post], 
                         thread_id=thread_id, 
                         replyto_id=replyto_id)

@app.route('/health')
def health_check():
    try:
        # データベース接続テスト
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        app.logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "database": "disconnected", "error": str(e)}), 500

if __name__ == "__main__":
    with app.app_context():
        try:
            # データベース接続テスト
            db.engine.connect()
            app.logger.info("Database connection successful")
            # テーブル作成
            db.create_all()
        except Exception as e:
            app.logger.error(f"Database connection failed: {str(e)}")
            raise

    if ENV == 'development':
        app.run(host='127.0.0.1', port=3000, debug=True)
    else:
        app.run(host='127.0.0.1', port=3000, debug=False) 