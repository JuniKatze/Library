# -*- coding: utf-8 -*-
from flask import Flask, request, redirect, url_for, render_template, session, flash
from contextlib import closing
from models import init_db, get_db, User, Teacher, LibException, OutOfQuota, HasBorrowed

app = Flask(__name__)
app.secret_key = "library_2025"


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    with closing(get_db()) as db:
        row = db.execute("SELECT * FROM user WHERE uid=?", (uid,)).fetchone()
        if not row:
            session.clear()
            return None
        cls = Teacher if row["role"] == "TEA" else User
        user = cls(**{k: row[k] for k in row.keys() if k != "role"})
        # 确保角色属性被正确设置
        user.role = row["role"]
        return user


# ---------- 登录/退出 ----------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            user = User.login(request.form["uid"], request.form["pwd"])
            session["uid"] = user.uid
            session["role"] = user.role
            return redirect("/index")
        except Exception:
            flash("账号或密码错误")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------- 一级菜单 ----------
@app.route("/index")
def index():
    user = current_user()
    if not user:
        return redirect("/")
    return render_template("index.html", user=user, role=session["role"])


# ---------- 二级：用户基本信息 + 修改 ----------
@app.route("/user/info")
def user_info():
    user = current_user()
    if not user:
        return redirect("/")
    # 教师：相关班级；学生：所属班级（从单独表读）
    if user.role == "TEA":
        with closing(get_db()) as db:
            classes = db.execute(
                "SELECT c.id FROM class c JOIN teacher_class tc ON c.id=tc.class_id WHERE tc.teacher_uid=?",
                (user.uid,),
            ).fetchall()
        class_list = [c[0] for c in classes]
    else:
        with closing(get_db()) as db:
            row = db.execute("SELECT class_id FROM student WHERE uid=?", (user.uid,)).fetchone()
            class_list = [row["class_id"]] if row and row["class_id"] else []
    return render_template("user_info.html", user=user, class_list=class_list)


@app.route("/user/update", methods=["POST"])
def user_update():
    user = current_user()
    if not user:
        return redirect("/")
    new_name = request.form.get("name", "").strip()
    new_age = request.form.get("age", "").strip()
    if new_name:
        try:
            user.name = new_name
            flash("姓名已更新")
        except ValueError as e:
            flash(str(e))
    if new_age:
        try:
            user.age = int(new_age)
            flash("年龄已更新")
        except (ValueError, TypeError) as e:
            flash("年龄必须是正整数")
    return redirect("/user/info")


# ---------- 二级：书籍查询和借阅（含已借未还 / 额度不足 即时提示） ----------
@app.route("/book/query")
def book_query():
    user = current_user()
    if not user:
        return redirect("/")
    with closing(get_db()) as db:
        cats = db.execute("SELECT DISTINCT category FROM book").fetchall()
        books = db.execute("SELECT * FROM book WHERE remain>0").fetchall()
    books_enum = [{"idx": i + 1, **dict(b)} for i, b in enumerate(books)]
    return render_template("book_list.html", categories=[c[0] for c in cats], books=books_enum)


@app.route("/book/category/<cat>")
def book_by_cat(cat):
    user = current_user()
    if not user:
        return redirect("/")
    with closing(get_db()) as db:
        books = db.execute("SELECT * FROM book WHERE category=? AND remain>0", (cat,)).fetchall()
    books_enum = [{"idx": i + 1, **dict(b)} for i, b in enumerate(books)]
    return render_template("book_list.html", categories=[], books=books_enum, cat=cat)


@app.route("/borrow", methods=["POST"])
def borrow():
    user = current_user()
    if not user:
        return redirect("/")
    try:
        user.borrow(request.form["isbn"])
        flash("借阅成功")
    except OutOfQuota as e:
        flash(str(e))
    except HasBorrowed as e:
        flash(str(e))
    except LibException as e:
        flash(str(e))
    return redirect("/book/query")


# ---------- 二级：已借阅书籍查询和归还 ----------
@app.route("/my/borrow")
def my_borrow():
    user = current_user()
    if not user:
        return redirect("/")
    borrows = user.current_borrow()
    borrows_enum = [{"idx": i + 1, **dict(b)} for i, b in enumerate(borrows)]
    return render_template("my_borrow.html", borrows=borrows_enum)


@app.route("/return/<int:borrow_id>")
def return_book(borrow_id):
    user = current_user()
    if not user:
        return redirect("/")
    try:
        user.return_book(borrow_id)
        flash("归还成功")
    except LibException as e:
        flash(str(e))
    return redirect("/my/borrow")


# ---------- 教师专用：班级管理 ----------
@app.route("/class")
def list_class():
    if session.get("role") != "TEA":
        flash("仅限教师")
        return redirect("/index")
    t = current_user()
    if not t:
        return redirect("/")
    with closing(get_db()) as db:
        classes = db.execute(
            "SELECT c.id FROM class c JOIN teacher_class tc ON c.id=tc.class_id WHERE tc.teacher_uid=?",
            (t.uid,),
        ).fetchall()
        all_classes = db.execute("SELECT id FROM class").fetchall()
    related = [c[0] for c in classes]
    unused = [c[0] for c in all_classes if c[0] not in related]
    return render_template("classes.html", related=related, unused=unused)


@app.route("/class/add", methods=["POST"])
def class_add():
    if session.get("role") != "TEA":
        return redirect("/index")
    t = current_user()
    if not t:
        return redirect("/")
    class_id = request.form.get("class_id", "").strip()
    if class_id:
        t.add_class(class_id)
        flash("已关联班级 " + class_id)
    return redirect("/class")


@app.route("/class/remove", methods=["POST"])
def class_remove():
    if session.get("role") != "TEA":
        return redirect("/index")
    t = current_user()
    if not t:
        return redirect("/")
    class_id = request.form.get("class_id", "").strip()
    if class_id:
        t.remove_class(class_id)
        flash("已取消关联 " + class_id)
    return redirect("/class")


# ---------- 教师专用：相关班级学生借书情况查询（三级菜单） ----------
@app.route("/teacher/class_borrow")
def teacher_class_borrow():
    """教师查询相关班级学生借书情况 - 第一步：显示班级列表"""
    if session.get("role") != "TEA":
        flash("仅限教师")
        return redirect("/index")

    t = current_user()
    if not t:
        return redirect("/")

    with closing(get_db()) as db:
        classes = db.execute(
            "SELECT c.id, c.name FROM class c JOIN teacher_class tc ON c.id=tc.class_id WHERE tc.teacher_uid=? ORDER BY c.id",
            (t.uid,)
        ).fetchall()

    # 转换为带序号的列表
    classes_enum = [{"idx": i + 1, "id": c["id"], "name": c["name"]} for i, c in enumerate(classes)]

    return render_template("teacher_class_borrow.html", classes=classes_enum)


@app.route("/teacher/class_borrow/<class_id>")
def teacher_class_students(class_id):
    """教师查询相关班级学生借书情况 - 第二步：显示班级学生列表"""
    if session.get("role") != "TEA":
        flash("仅限教师")
        return redirect("/index")

    t = current_user()
    if not t:
        return redirect("/")

    # 验证教师是否关联该班级
    with closing(get_db()) as db:
        is_related = db.execute(
            "SELECT 1 FROM teacher_class WHERE teacher_uid=? AND class_id=?",
            (t.uid, class_id)
        ).fetchone()
        if not is_related:
            flash("无权查看该班级")
            return redirect("/teacher/class_borrow")

        # 获取班级信息
        class_info = db.execute("SELECT id, name FROM class WHERE id=?", (class_id,)).fetchone()

        # 获取该班级的学生
        students = db.execute(
            "SELECT u.uid, u.name, u.sex, u.age FROM user u JOIN student s ON u.uid=s.uid WHERE s.class_id=? AND u.role='STU' ORDER BY u.uid",
            (class_id,)
        ).fetchall()

    students_enum = [{"idx": i + 1, "uid": s["uid"], "name": s["name"], "sex": s["sex"], "age": s["age"]} for i, s in
                     enumerate(students)]

    return render_template("teacher_class_students.html", class_info=class_info, students=students_enum)


@app.route("/teacher/student_borrow/<class_id>/<student_uid>")
def teacher_student_borrow(class_id, student_uid):
    """教师查询相关班级学生借书情况 - 第三步：显示学生借书详情"""
    if session.get("role") != "TEA":
        flash("仅限教师")
        return redirect("/index")

    t = current_user()
    if not t:
        return redirect("/")

    # 验证教师是否关联该班级
    with closing(get_db()) as db:
        is_related = db.execute(
            "SELECT 1 FROM teacher_class WHERE teacher_uid=? AND class_id=?",
            (t.uid, class_id)
        ).fetchone()
        if not is_related:
            flash("无权查看该班级")
            return redirect("/teacher/class_borrow")

        # 验证学生是否在该班级
        is_in_class = db.execute(
            "SELECT 1 FROM student WHERE uid=? AND class_id=?",
            (student_uid, class_id)
        ).fetchone()
        if not is_in_class:
            flash("学生不在该班级")
            return redirect(f"/teacher/class_borrow/{class_id}")

        # 获取学生信息
        student_info = db.execute("SELECT uid, name FROM user WHERE uid=?", (student_uid,)).fetchone()

        # 获取班级信息
        class_info = db.execute("SELECT id, name FROM class WHERE id=?", (class_id,)).fetchone()

        # 获取学生借书详情（与3.3相同的信息）
        borrows = db.execute(
            """SELECT b.id,
                      b.borrow_date,
                      b.due_date,
                      bo.isbn,
                      bo.name AS book_name,
                      bo.authors,
                      bo.publisher,
                      bo.keywords
               FROM borrow b
                        JOIN book bo ON b.isbn = bo.isbn
               WHERE b.uid = ?
                 AND b.returned = 0
               ORDER BY b.due_date""",
            (student_uid,)
        ).fetchall()

    borrows_enum = [{"idx": i + 1, **dict(b)} for i, b in enumerate(borrows)]

    return render_template("teacher_student_borrow.html",
                           class_info=class_info,
                           student_info=student_info,
                           borrows=borrows_enum)


# ---------------- 启动 ----------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)