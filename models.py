# -*- coding: utf-8 -*-
"""
实体类与数据库初始化
PEP8 + 关键注释
"""
import datetime
import pathlib
import sqlite3
from contextlib import closing
from werkzeug.security import generate_password_hash, check_password_hash

DB_FILE = pathlib.Path(__file__).with_name("library.db")


# ---------------- 异常 ----------------
class LibException(Exception):
    """图书馆业务异常基类"""


class AuthFail(LibException):
    """登录失败"""


class OutOfQuota(LibException):
    """借书额度已满"""


class HasBorrowed(LibException):
    """已借未还"""


class NoBook(LibException):
    """无库存"""


# ---------------- 工具 ----------------
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- 实体 ----------------
class User:
    """公共基类：用户"""

    def __init__(self, uid, name, sex, age, college, password, **kw):
        self.uid = uid
        self._name = name
        self.sex = sex
        self._age = age
        self.college = college
        self._pwd_hash = password
        self.role = kw.get("role", "STU")  # 默认学生

    # 获取借书额度
    @property
    def quota(self):
        """根据角色返回借书额度"""
        if self.role == "TEA":
            return 4
        else:
            return 2

    # ====== 登录（唯一密码校验入口） ======
    @staticmethod
    def login(uid, pwd):
        with closing(get_db()) as db:
            row = db.execute("SELECT * FROM user WHERE uid=?", (uid,)).fetchone()
            if not row or not check_password_hash(row["password"], pwd):
                raise AuthFail
            # 根据角色创建正确的实例
            if row["role"] == "TEA":
                user = Teacher(**{k: row[k] for k in row.keys()})
            else:
                user = Student(**{k: row[k] for k in row.keys()})
            return user

    # ====== 借书（含额度硬检查 + 已借未还检查） ======
    def borrow(self, isbn):
        with closing(get_db()) as db:
            # 1. 检查书是否存在且有余量
            book = db.execute("SELECT * FROM book WHERE isbn=?", (isbn,)).fetchone()
            if not book or book["remain"] <= 0:
                raise NoBook("书籍不存在或库存不足")

            # 2. 检查是否已借过同一本书且未还
            if db.execute(
                    "SELECT 1 FROM borrow WHERE uid=? AND isbn=? AND returned=0", (self.uid, isbn)
            ).fetchone():
                raise HasBorrowed("已借过此书且未归还")

            # 3. 检查额度
            borrowed = db.execute(
                "SELECT COUNT(*) AS c FROM borrow WHERE uid=? AND returned=0", (self.uid,)
            ).fetchone()["c"]
            if borrowed >= self.quota:
                raise OutOfQuota(f"额度已满（教师 4 本/学生 2 本），当前已借 {borrowed} 本")

            # 4. 执行借阅
            today = datetime.date.today()
            due = today + datetime.timedelta(days=90)
            db.execute(
                "INSERT INTO borrow(uid,isbn,borrow_date,due_date,returned) VALUES(?,?,?,?,0)",
                (self.uid, isbn, today, due),
            )
            db.execute("UPDATE book SET remain=remain-1 WHERE isbn=?", (isbn,))
            db.commit()

    # ====== 还书 ======
    def return_book(self, borrow_id):
        with closing(get_db()) as db:
            br = db.execute(
                "SELECT * FROM borrow WHERE id=? AND uid=? AND returned=0", (borrow_id, self.uid)
            ).fetchone()
            if not br:
                raise LibException("记录不存在或已归还")
            db.execute("UPDATE borrow SET returned=1 WHERE id=?", (borrow_id,))
            db.execute("UPDATE book SET remain=remain+1 WHERE isbn=?", (br["isbn"],))
            db.commit()

    # ====== 当前在借 ======
    def current_borrow(self):
        with closing(get_db()) as db:
            sql = """SELECT b.*, bo.name, bo.authors, bo.publisher, bo.keywords
                     FROM borrow b \
                              JOIN book bo ON b.isbn = bo.isbn
                     WHERE b.uid = ? \
                       AND b.returned = 0 \
                     ORDER BY b.due_date"""
            return db.execute(sql, (self.uid,)).fetchall()

    # ====== 公共修改方法（姓名/年龄） ======
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not value:
            raise ValueError("姓名不能为空")
        with closing(get_db()) as db:
            db.execute("UPDATE user SET name=? WHERE uid=?", (value, self.uid))
            db.commit()
        self._name = value

    @property
    def age(self):
        return self._age

    @age.setter
    def age(self, value):
        if value <= 0:
            raise ValueError("年龄必须为正整数")
        with closing(get_db()) as db:
            db.execute("UPDATE user SET age=? WHERE uid=?", (value, self.uid))
            db.commit()
        self._age = value


class Teacher(User):
    """教师派生类"""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.join_year = kw.get("join_year", 2020)
        self.role = "TEA"

    # --- 关联/取消班级 ---
    def add_class(self, class_id):
        with closing(get_db()) as db:
            db.execute("INSERT OR IGNORE INTO teacher_class(teacher_uid, class_id) VALUES(?,?)", (self.uid, class_id))
            db.commit()

    def remove_class(self, class_id):
        with closing(get_db()) as db:
            db.execute("DELETE FROM teacher_class WHERE teacher_uid=? AND class_id=?", (self.uid, class_id))
            db.commit()

    def class_borrow(self, class_id):
        with closing(get_db()) as db:
            sql = """SELECT st.uid, st.name, bo.name AS book_name, b.due_date
                     FROM student st
                              JOIN borrow b ON st.uid = b.uid
                              JOIN book bo ON b.isbn = bo.isbn
                     WHERE st.class_id = ? \
                       AND b.returned = 0
                     ORDER BY st.uid, b.due_date"""
            return db.execute(sql, (class_id,)).fetchall()


class Student(User):
    """学生派生类"""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.role = "STU"


# ---------------- 数据库初始化 ----------------
def init_db():
    with closing(get_db()) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS user
            (
                uid
                TEXT
                PRIMARY
                KEY,
                name
                TEXT
                NOT
                NULL,
                sex
                TEXT,
                age
                INTEGER,
                college
                TEXT,
                join_year
                INTEGER,
                password
                TEXT
                NOT
                NULL,
                role
                TEXT
                CHECK (
                role
                IN
            (
                'TEA',
                'STU'
            )) NOT NULL
                );
            CREATE TABLE IF NOT EXISTS class
            (
                id
                TEXT
                PRIMARY
                KEY,
                name
                TEXT
            );
            CREATE TABLE IF NOT EXISTS student
            (
                uid
                TEXT
                PRIMARY
                KEY,
                class_id
                TEXT,
                FOREIGN
                KEY
            (
                uid
            ) REFERENCES user
            (
                uid
            )
                );
            CREATE TABLE IF NOT EXISTS teacher_class
            (
                teacher_uid
                TEXT,
                class_id
                TEXT,
                PRIMARY
                KEY
            (
                teacher_uid,
                class_id
            ),
                FOREIGN KEY
            (
                teacher_uid
            ) REFERENCES user
            (
                uid
            )
                );
            CREATE TABLE IF NOT EXISTS book
            (
                isbn
                TEXT
                PRIMARY
                KEY,
                name
                TEXT
                NOT
                NULL,
                category
                TEXT
                CHECK (
                category
                IN
            (
                'CS',
                'MATH',
                'PHY',
                'LIT'
            )),
                authors TEXT,
                publisher TEXT,
                keywords TEXT,
                remain INTEGER
                );
            CREATE TABLE IF NOT EXISTS borrow
            (
                id
                INTEGER
                PRIMARY
                KEY
                AUTOINCREMENT,
                uid
                TEXT,
                isbn
                TEXT,
                borrow_date
                DATE,
                due_date
                DATE,
                returned
                INTEGER
                DEFAULT
                0,
                FOREIGN
                KEY
            (
                uid
            ) REFERENCES user
            (
                uid
            ),
                FOREIGN KEY
            (
                isbn
            ) REFERENCES book
            (
                isbn
            )
                );
            """
        )
        # 清空现有数据
        db.execute("DELETE FROM borrow")
        db.execute("DELETE FROM book")
        db.execute("DELETE FROM teacher_class")
        db.execute("DELETE FROM student")
        db.execute("DELETE FROM class")
        db.execute("DELETE FROM user")

        # 初始数据
        teachers = [
            ("T001", "张老师", "女", 40, "数学学院", 2010, "123456", "TEA"),
            ("T002", "李老师", "男", 38, "数学学院", 2015, "123456", "TEA"),
        ]
        students = [
            ("S001", "Alice", "女", 19, "数学学院", None, "111", "STU"),
            ("S002", "Bob", "男", 20, "数学学院", None, "111", "STU"),
            ("S003", "Carol", "女", 19, "数学学院", None, "111", "STU"),
            ("S004", "Dave", "男", 21, "数学学院", None, "111", "STU"),
            ("S005", "Eve", "女", 20, "数学学院", None, "111", "STU"),
        ]
        books = [
            ("9787111234567", "Python 编程", "CS", "Guido, 某人", "机械工业", "Python 入门", 5),
            ("9787042345678", "数学分析新讲", "MATH", "张三", "高等教育", "数学 分析", 3),
            ("9787301123456", "普通物理", "PHY", "李四", "清华大学", "物理 基础", 4),
            ("9787021456789", "围城", "LIT", "钱钟书", "人民文学", "小说 近代", 6),
            ("9787031234567", "线性代数", "MATH", "李永乐", "科学", "线代 考研", 4),
            ("9787112345678", "C++ Primer", "CS", "Lippman", "机械工业", "C++ 入门", 5),
            ("9787043456789", "大学物理", "PHY", "赵凯华", "高等教育", "物理 通识", 3),
            ("9787022567890", "红楼梦", "LIT", "曹雪芹", "人民文学", "古典 四大", 6),
            ("9787302123456", "算法导论", "CS", "CLRS", "清华大学", "算法 经典", 2),
            ("9787011345678", "近代史", "LIT", "蒋廷黻", "人民", "历史 近代", 4),
        ]

        for uid, name, sex, age, college, jy, pwd, role in teachers + students:
            db.execute(
                "INSERT INTO user(uid,name,sex,age,college,join_year,password,role) VALUES(?,?,?,?,?,?,?,?)",
                (uid, name, sex, age, college, jy, generate_password_hash(pwd), role),
            )

        # 学生班级
        db.execute("INSERT INTO student(uid, class_id) VALUES(?,?)", ("S001", "C001"))
        db.execute("INSERT INTO student(uid, class_id) VALUES(?,?)", ("S002", "C001"))
        db.execute("INSERT INTO student(uid, class_id) VALUES(?,?)", ("S003", "C002"))
        db.execute("INSERT INTO student(uid, class_id) VALUES(?,?)", ("S004", "C002"))
        db.execute("INSERT INTO student(uid, class_id) VALUES(?,?)", ("S005", "C001"))

        for b in books:
            db.execute(
                "INSERT OR IGNORE INTO book(isbn,name,category,authors,publisher,keywords,remain) VALUES(?,?,?,?,?,?,?)",
                b,
            )

        # 班级
        classes = [("C001", "2023级数学1班"), ("C002", "2023级数学2班")]
        for cid, cname in classes:
            db.execute("INSERT OR IGNORE INTO class(id, name) VALUES(?,?)", (cid, cname))

        # 教师关联班级
        db.execute("INSERT OR IGNORE INTO teacher_class(teacher_uid, class_id) VALUES(?,?)", ("T001", "C001"))
        db.execute("INSERT OR IGNORE INTO teacher_class(teacher_uid, class_id) VALUES(?,?)", ("T001", "C002"))

        db.commit()