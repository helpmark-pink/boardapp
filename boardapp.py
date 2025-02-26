from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

app = Flask(__name__, template_folder='templates')

# 環境設定
ENV = os.getenv('FLASK_ENV', 'development')
DEBUG = ENV == 'development'

# セキュリティ設定
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24))

# PostgreSQLのURLをSQLAlchemyの形式に変換
database_url = os.getenv('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///board.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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

# データベース初期化
with app.app_context():
    db.create_all()

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

# レート制限をルートに適用
@limiter.limit("5 per minute")
@app.route("/", methods=["GET", "POST"])
def top():
    if request.method == "POST":
        thread_title = request.form.get("thread-title")
        if thread_title:
            new_thread = Thread(title=thread_title)
            db.session.add(new_thread)
            db.session.commit()
            return redirect(url_for("top"))
    
    threads = Thread.query.order_by(Thread.created_at.desc()).all()
    return render_template("threads.html", threads_fetches=threads)

@limiter.limit("20 per minute")
@app.route("/<int:thread_id>", methods=["GET", "POST"])
def posts(thread_id):
    thread = Thread.query.get_or_404(thread_id)
    
    if request.method == "POST":
        name = request.form.get("post-name")
        message = request.form.get("post-message")
        
        if name and message:
            post_id = Post.query.filter_by(thread_id=thread_id).count() + 1
            new_post = Post(
                thread_id=thread_id,
                post_id=post_id,
                name=name,
                message=message
            )
            db.session.add(new_post)
            db.session.commit()
            return redirect(url_for("posts", thread_id=thread_id))
    
    posts = Post.query.filter_by(thread_id=thread_id).order_by(Post.date.asc()).all()
    return render_template("posts.html", thread_title=thread.title, posts_fetches=posts, thread_id=thread_id)

@limiter.limit("10 per minute")
@app.route("/<int:thread_id>/replyto-<int:replyto_id>", methods=["GET", "POST"])
def reply(thread_id, replyto_id):
    thread = Thread.query.get_or_404(thread_id)
    original_post = Post.query.filter_by(thread_id=thread_id, post_id=replyto_id).first_or_404()
    
    if request.method == "POST":
        name = request.form.get("post-name")
        message = request.form.get("post-message")
        
        if name and message:
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
            return redirect(url_for("posts", thread_id=thread_id))
    
    return render_template("reply.html", 
                         thread_title=thread.title, 
                         posts_fetches=[original_post], 
                         thread_id=thread_id, 
                         replyto_id=replyto_id)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    if ENV == 'development':
        app.run(host='127.0.0.1', port=3000, debug=True)
    else:
        app.run(host='127.0.0.1', port=3000, debug=False) 