import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_ckeditor import CKEditor
from forms import CreateRegisterForm, CreatePostForm, CreateLoginForm, CommentForm
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user
from functools import wraps
# relationship database
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
# using of avatar photo
from flask_gravatar import Gravatar
import os
import psycopg2

today = datetime.datetime.now().strftime("%B %d,%Y")

# ------------------ Create APP------------------#
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
ckeditor = CKEditor(app)
Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)
gravatar = Gravatar(app, size=100, rating='g', default='retro', force_default=False,
                    force_lower=False, use_ssl=False, base_url=None)


# create user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# ------------------ Create DB------------------#
# Debugging issue between heroku and postgres
# uri = os.getenv("DATABASE_URL")  # or other relevant config var
# if uri.startswith("postgres://"):
#     uri = uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///posts.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# Configure table / Relationship database
# Parent
class User(UserMixin, db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    # Parent for BlogPost
    posts = relationship("BlogPost", back_populates="author")
    # Parent for comment
    comments = relationship("Comment", back_populates="comment_user")

    email = db.Column(db.String(250), unique=True, nullable=False)
    name = db.Column(db.String(250), nullable=False)
    password = db.Column(db.String(250), nullable=False)


# Child/Parent
class BlogPost(db.Model):
    __tablename__ = 'blog_post'
    id = db.Column(db.Integer, primary_key=True)
    # Child for User
    author_id = db.Column(Integer, db.ForeignKey('user.id'))
    author = relationship("User", back_populates="posts")
    # Parent for Comment
    comments = relationship("Comment", back_populates="comment_blog")

    title = db.Column(db.String(250), nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)


# Child
class Comment(db.Model):
    __tablename__ = 'comment'
    id = db.Column(db.Integer, primary_key=True)
    # Child for User
    comment_user_id = db.Column(Integer, db.ForeignKey('user.id'))
    comment_user = relationship("User", back_populates="comments")
    # Child for BlogPost
    comment_blog_id = db.Column(Integer, db.ForeignKey('blog_post.id'))
    comment_blog = relationship("BlogPost", back_populates="comments")

    text = db.Column(db.String(1000), nullable=False)


with app.app_context():
    db.create_all()


# ------------------ Web Set------------------#
def admin_only(function):
    @ wraps(function)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.get_id() != '1':
            return abort(403)
        return function(*args, **kwargs)
    return decorated_function


@app.route('/')
def get_all_posts():
    posts = db.session.query(BlogPost).all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


@app.route("/post/<int:post_id>", methods=['GET', 'POST'])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('Please login or register to comment!')
            return redirect(url_for('login'))
        else:
            if current_user.is_authenticated:
                new_comment = Comment(
                    comment_user_id=int(current_user.get_id()),
                    comment_blog_id=post_id,
                    text=comment_form.body.data
                )
                db.session.add(new_comment)
                db.session.commit()
                return redirect(url_for('show_post', post_id=post_id))
    return render_template("post.html", post=requested_post, form=comment_form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    register_form = CreateRegisterForm()
    if register_form.validate_on_submit():
        # Check if registered
        register_email = register_form.email.data
        if User.query.filter_by(email=register_email).first():
            flash("You've already signed up with email. Please log in.")
            return redirect(url_for('login'))

        # create new user
        new_user = User(
            email=register_email,
            name=register_form.name.data,
            password=generate_password_hash(register_form.password.data, salt_length=8)
        )
        db.session.add(new_user)
        db.session.commit()

        # Login user
        login_user(new_user)

        return redirect(url_for('get_all_posts', login=True))
    return render_template("register.html", form=register_form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = CreateLoginForm()
    if login_form.validate_on_submit():
        user = User.query.filter_by(email=login_form.email.data).first()
        if not user:
            flash("That email does not exist. Please try again.")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, login_form.password.data):
            flash("Wrong password. Please try again.")
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_posts', login=True))
    return render_template("login.html", form=login_form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/new-post", methods=['POST', 'GET'])
@ admin_only
def add_post():
    add_form = CreatePostForm()
    if add_form.validate_on_submit():
        new_post = BlogPost(
            title=add_form.title.data,
            subtitle=add_form.subtitle.data,
            date=today,
            body=add_form.body.data,
            img_url=request.form.get('img_url'),
            author_id=current_user.id,
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for('get_all_posts'))
    return render_template('make-post.html', form=add_form)


@app.route("/edit-post/<int:post_id>", methods=['POST', 'GET'])
@ admin_only
def edit_post(post_id):
    post_to_edit = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post_to_edit.title,
        subtitle=post_to_edit.subtitle,
        img_url=post_to_edit.img_url,
        body=post_to_edit.body,
    )
    if edit_form.validate_on_submit():
        post_to_edit.title = edit_form.title.data
        post_to_edit.subtitle = edit_form.subtitle.data
        post_to_edit.img_url = edit_form.img_url.data
        post_to_edit.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))
    return render_template('make-post.html', form=edit_form, edit=True)


@app.route("/delete/<int:post_id>", methods=['POST', 'GET'])
@ admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)
