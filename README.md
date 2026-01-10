# 大作业实验报告

项目Github地址为：`https://github.com/JuniKatze/Library.git`。

注意：该项目由`uv`管理，需要下载了`uv`。

## 系统设计

这是一个用`uv`管理的，基于`Flask`框架的图书管理项目。

项目源码（含数据库）目录如下：

```text
Library/
├── app.py                            # 项目的入口文件，也是整个项目路由
├── models.py                         # 实现User基类，教师派生类和学生派生类，实现 ORM 和借书，还书等各种类方法
├── templates                         # 各种静态HTML网页
│   ├── login.html                    # 一级菜单"/"，登陆页面
│   ├── index.html                    # 二级菜单"index"，用户界面
│   ├── user_info.html                # 三级菜单：用户基本信息
│   ├── book_list.html                # 三级菜单：书籍查询和借阅
│   ├── my_borrow.html                # 三级菜单：已借阅书籍查询和归还
│   ├── teacher_class_borrow.html     # 三级菜单：相关班级查询列表
│   ├── teacher_class_students.html   # 四级菜单：相关班级学生列表
│   ├── teacher_student_borrow.html   # 五级菜单：特定学生借阅情况
│   ├── classes.html                  # 三级菜单：相关班级管理
├── README.md                         # 报告
└── library.db                        # Sqlite数据库，可自动生成
```

## 软件使用说明

0. 准备`uv`

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

1. 从`github`上面克隆到本地

```shell
git clone https://github.com/JuniKatze/Library.git
```

2. 进入项目

```shell
cd Library
```

3. 同步相关虚拟环境和依赖

```shell
uv sync
```

4. 激活虚拟环境

```shell
source .venv/bin/activate
```

5. 运行项目

```shell
uv run python app.py
```

6. 注意：项目克隆到本地没有数据库，但是代码会自动初始化数据库，并写入初始数据

## 软件测试结果截图及其说明

见视频

## 总结

这是一个清晰明了，功能基本健全的图书管理项目，写这个项目也算是我学习Flask的一个过程，我收获良多。
