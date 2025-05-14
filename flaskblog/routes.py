import os
import secrets
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort
from flaskblog import app, db, bcrypt, mail
from flaskblog.forms import (RegistrationForm, LoginForm, UpdateAccountForm,
                             PostForm, RequestResetForm, ResetPasswordForm, NBAStatsForm)
from flaskblog.models import User, Post
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message
from flask import jsonify

import os
import pandas as pd
import pickle
# from sklearn.preprocessing import StandardScaler
import numpy as np

from flaskblog.model.model import predict_ffnn

# with open(os.getcwd()+'/flaskblog/trained_ffnn.pkl', 'rb') as f:
#     trained_ffnn = pickle.load(f)

data = pd.read_csv(os.getcwd()+'/flaskblog/nba_data_23-24.csv')
data.rename(columns={
    "FG%":	"FG_PCT",
    "3P%":	"FG3_PCT",
    "FT%":	"FT_PCT",
    "DREB":	"DREB",
    "REB":	"REB",
    "STL":	"STL",
    "TOV":	"TO",
    "PF":	"PF",
    "+/-":	"PLUS_MINUS",
    "W": "NEXT_W"
}, inplace=True)

working_df = data[["TEAM","FG_PCT", "FG3_PCT", "FT_PCT", "DREB", "REB", "STL", "TO", "PF", "PLUS_MINUS", "NEXT_W"]].copy()

def standardize_data(data):
    features = ["FG_PCT", "FG3_PCT", "FT_PCT", "DREB", "REB", "STL", "TO", "PF", "PLUS_MINUS"]
    temp = data[features].copy()
    means = temp.mean()
    stds = temp.std(ddof=0)  # ddof=0 for population std (to match sklearn behavior)
    preprocess = (temp - means) / stds
    data_scaled = pd.DataFrame(preprocess)
    return data_scaled

@app.route("/update_team_stats", methods=["POST"])
# @login_required
def update_team_stats():
    form_data = request.form
    try:
        input_data = {
            "FG_PCT": float(form_data["FG_PCT"]),
            "FG3_PCT": float(form_data["FG3_PCT"]),
            "FT_PCT": float(form_data["FT_PCT"]),
            "DREB": float(form_data["DREB"]),
            "REB": float(form_data["REB"]),
            "STL": float(form_data["STL"]),
            "TO": float(form_data["TO"]),
            "PF": float(form_data["PF"]),
            "PLUS_MINUS": float(form_data["PLUS_MINUS"]),
            "NEXT_W": 0  # placeholder
        }
        for field in input_data:
            working_df.loc[working_df['TEAM'] == form_data["TEAM"], field] = input_data[field]
        print(working_df[working_df['TEAM'] == form_data["TEAM"]]['FG_PCT'])
        data_scaled = standardize_data(working_df.iloc[:,1:])
        y_pred = predict_ffnn(data_scaled)
        
        # updated_pred = int(np.rint(y_pred[0]))
        # flash(f'Updated prediction for {form_data["TEAM"]}: {updated_pred} wins.', 'success')
        working_df['Predicted_Wins'] = np.rint(y_pred)
        predictions_df = working_df.sort_values(by="Predicted_Wins", ascending=False)
        predictions_df.dropna(inplace=True)

        return render_template('home2.html', predictions_df=predictions_df)

    except Exception as e:
        flash(f"Error processing input: {str(e)}", "danger")

    return redirect(url_for("home"))


@app.route("/")
@app.route("/home")
def home():
    # page = request.args.get('page', 1, type=int)
    # posts = Post.query.order_by(Post.date_posted.desc()).paginate(page=page, per_page=5)    
    data_scaled = standardize_data(working_df.iloc[:,1:])
    y_pred = predict_ffnn(data_scaled)

    working_df['Predicted_Wins'] = np.rint(y_pred)
    predictions_df = working_df.sort_values(by="Predicted_Wins", ascending=False)
    predictions_df.dropna(inplace=True)
    print(predictions_df.columns)

    return render_template('home2.html', predictions_df=predictions_df)

@app.route("/stats_form", methods=["GET", "POST"])
def nba_stats_form():
    form = NBAStatsForm()
    extracted_data = {}
    prediction = False
    if form.validate_on_submit():
        team = form.Team.data
        extracted_data = {
            "FG_PCT": form.FG_PCT.data,
            "FG3_PCT": form.FG3_PCT.data,
            "FT_PCT": form.FT_PCT.data,
            "DREB": form.DREB.data,
            "REB": form.REB.data,
            "STL": form.STL.data,
            "TO": form.TO.data,
            "PF": form.PF.data,
            "PLUS_MINUS": form.PLUS_MINUS.data,
            "NEXT_W": form.NEXT_W.data
        }
        df = pd.DataFrame([extracted_data])
        data_scaled = standardize_data(df)
        y_pred = predict_ffnn(data_scaled)
        df['Predicted_Wins'] = np.rint(y_pred)
        df['TEAM'] = team
        predictions_df = df[['TEAM', 'Predicted_Wins']].sort_values(by="Predicted_Wins", ascending=False)
        predictions_df.dropna(inplace=True)
        prediction = True
    
    return render_template("predict_form.html", form=form, prediction=prediction, predictions_df=predictions_df)

@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)

    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)


@app.route("/post/new", methods=['GET', 'POST'])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(title=form.title.data, content=form.content.data, author=current_user)
        db.session.add(post)
        db.session.commit()
        flash('Your post has been created!', 'success')
        return redirect(url_for('home'))
    return render_template('create_post.html', title='New Post',
                           form=form, legend='New Post')


@app.route("/post/<int:post_id>")
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post.html', title=post.title, post=post)


@app.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = form.content.data
        db.session.commit()
        flash('Your post has been updated!', 'success')
        return redirect(url_for('post', post_id=post.id))
    elif request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
    return render_template('create_post.html', title='Update Post',
                           form=form, legend='Update Post')


@app.route("/post/<int:post_id>/delete", methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted!', 'success')
    return redirect(url_for('home'))


@app.route("/user/<string:username>")
def user_posts(username):
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user)\
        .order_by(Post.date_posted.desc())\
        .paginate(page=page, per_page=5)
    return render_template('user_posts.html', posts=posts, user=user)


def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender='noreply@demo.com',
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made.
'''
    mail.send(msg)


@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html', title='Reset Password', form=form)


@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_password
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', title='Reset Password', form=form)
