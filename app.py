from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime


app = Flask(__name__)
app.secret_key = "supersecretkey"

# Подключение к MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["freelancehub"]
users = db["users"]
projects = db["projects"]
reviews = db["reviews"]
# ---------------- Регистрация ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        role = request.form["role"]
        skills = request.form.get("skills", "")

        existing_user = users.find_one({"username": username})
        if existing_user:
            flash("Пользователь уже существует!")
            return redirect(url_for("register"))

        users.insert_one({
            "username": username,
            "password": password,
            "role": role,
            "skills": skills
        })
        flash("Регистрация успешна! Теперь войдите.")
        return redirect(url_for("login"))
    return render_template("register.html")
# ---------------- Вход ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = db.users.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            session["username"] = username
            session["role"] = user["role"]
            return redirect(url_for("index"))
        flash("Неверный логин или пароль!")
    return render_template("login.html")

# ---------------- Главная страница ----------------
@app.route("/")
def index():
    projects = db.projects.find()
    return render_template("index.html", projects=projects)


# ----------------Поик-------------------------

@app.route("/search", methods=["GET", "POST"])
def search():
    # получаем query и приводим к строке
    if request.method == "POST":
        query = (request.form.get("query") or "").strip()
    else:
        query = (request.args.get("query") or "").strip()

    results = []
    if query:
        # ищем пользователей с ролью executor или freelancer
        role_filter = {"$in": ["executor", "freelancer", "freelancer "]}  # немного защитим от опечаток
        # основной фильтр: ищем по username или по skills (регулярка, case-insensitive)
        search_filter = {
            "role": {"$in": ["executor", "freelancer"]},
            "$or": [
                {"username": {"$regex": query, "$options": "i"}},
                {"skills": {"$regex": query, "$options": "i"}}
            ]
        }
        results = list(users.find(search_filter))

    return render_template("search.html", results=results, query=query)

##-------------user-------------------
@app.route("/user/<username>", methods=["GET", "POST"])
def user_profile(username):
    # найдем пользователя по username
    user = users.find_one({"username": username})
    if not user:
        flash("Пользователь не найден.")
        return redirect(url_for("index"))

    # добавление отзыва (сохранить в коллекции reviews)
    if request.method == "POST":
        if "username" not in session:
            flash("Чтобы оставлять отзывы — войдите в систему.")
        return redirect(url_for("login"))

    # Проверяем роль
    if session.get("role") != "client":
        flash("Только клиенты могут оставлять отзывы.")
        return redirect(url_for("user_profile", username=username))

    review_text = request.form.get("review", "").strip()
    if review_text:
        reviews.insert_one({
            "user_username": username,
            "author": session.get("username"),
            "review": review_text,
            "created_at": datetime.utcnow()
        })
        flash("Отзыв добавлен.")
        return redirect(url_for("user_profile", username=username))

    # получить отзывы для этого пользователя
    user_reviews = list(reviews.find({"user_username": username}).sort("created_at", -1))
    return render_template("profile.html", user=user, reviews=user_reviews)

# ---------------- Список проектов ----------------
@app.route("/projects")
def projects():
    projects = db.projects.find()
    return render_template("projects.html", projects=projects)

# ---------------- Добавление проекта ----------------
@app.route("/add_project", methods=["GET", "POST"])
def add_project():
    if "username" not in session:
        flash("Сначала войдите в систему!")
        return redirect(url_for("login"))

    # Ограничение по роли
    if session.get("role") != "freelancer":
        flash("Только фрилансеры могут публиковать проекты.")
        return redirect(url_for("index"))

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        client = session["username"]

        db.projects.insert_one({
            "title": title,
            "description": description,
            "client": client,
            "created_at": datetime.utcnow()
        })
        flash("Проект опубликован!")
        return redirect(url_for("index"))

    return render_template("add_project.html")

# ---------------- Выход ----------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Вы вышли из системы.")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
