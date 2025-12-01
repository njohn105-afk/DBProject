from flask import Flask, render_template, request, redirect, session
import mysql.connector

app = Flask(__name__)
app.secret_key = "secret_key_test"

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="university"
    )

# vars

CURRENT_YEAR = 2022
CURRENT_SEMESTER = "Spring"

#ADMIN_MODE = True

# TODO:
#  Add the necessary checks/redirects for student/instructor/admin mode
#  More checks to prevent incomplete/error queries (deleting department with instructors in it)
#  Basic css styling for all templates

# Login setup instructions
# 


################### LOGIN

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor(dictionary=True)

        # Query to find the associated user
        query = """
            SELECT username, role, linked_id
            FROM users
            WHERE username = %s
            AND password_hash = SHA2(%s, 256)
        """
        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        if not user:
            return render_template(
                "message.html",
                message="Error: Invalid username or password",
                category="error",
                redirect_url="/login"
            )

        # Store session info for access later
        session["username"] = user["username"]
        session["role"] = user["role"]
        session["linked_id"] = user["linked_id"]

        # Redirect to portal based on role
        if user["role"] == "student":
            return redirect("/student-portal")
        elif user["role"] == "instructor":
            return redirect("/instructor-portal")
        elif user["role"] == "admin":
            return redirect("/admin/course")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")



################### STUDENT

@app.route("/")
def index():
    return redirect("/login");

# Main student access area (dashboard)
# Displays links to all functions (register class, drop class, etc)
@app.route("/student-portal")
def student_portal():
    if session.get("role") != "student":
        return redirect("/login")
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    STUDENT_ID = session["linked_id"]

    cursor.execute("""
        SELECT ID, name, dept_name 
        FROM student
        WHERE ID = %s
    """, (STUDENT_ID,))
    student = cursor.fetchone()

    return render_template("student/student_portal.html", student=student)


# Check final grades
@app.route("/student-portal/grades")
def grades():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if session.get("role") != "student":
        return redirect("/login")
    
    STUDENT_ID = session["linked_id"]

    cursor.execute("SELECT * FROM takes WHERE ID = %s;", (STUDENT_ID,))
    rows = cursor.fetchall()

    return render_template("/student/grades.html", rows=rows)

# Check courses based on semester 
# TODO: if year and semester match the current then its status: active
@app.route("/student-portal/courses", methods=["GET", "POST"])
def courses():
    selected_semester = request.form.get("semester")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if session.get("role") != "student":
        return redirect("/login")
    
    STUDENT_ID = session["linked_id"]

    query = """
        SELECT s.ID, s.name, t.course_id, t.semester, t.year, t.sec_id, t.grade
        FROM student s
        JOIN takes t ON s.ID = t.ID
        WHERE s.ID = %s
    """

    params = [STUDENT_ID]

    if selected_semester and selected_semester != "all":
        query += " AND t.semester = %s"
        params.append(selected_semester)

    cursor.execute(query, params)
    semester_rows = cursor.fetchall()

    for row in semester_rows:
        if row["year"] == CURRENT_YEAR and row["semester"] == CURRENT_SEMESTER:
            row["status"] = "Active"
        else:
            row["status"] = "Completed"

    cursor.execute("""
        SELECT DISTINCT semester
        FROM takes
        WHERE ID = %s
    """, (STUDENT_ID,))
    semesters = cursor.fetchall()

    return render_template(
        "/student/courses.html",
        student_id = STUDENT_ID,
        semesters = semesters,
        semester_rows = semester_rows,
        selected_semester = selected_semester,
    )

# Check section information
@app.route("/student-portal/section")
def section():
    course_id = request.args.get("course_id")
    sec_id    = request.args.get("sec_id")
    semester  = request.args.get("semester")
    year      = request.args.get("year")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if session.get("role") != "student":
        return redirect("/login")


    query = """
        SELECT s.building, s.room_number, s.time_slot_id
        FROM section s
        WHERE s.course_id = %s
        AND s.sec_id    = %s
        AND s.semester  = %s
        AND s.year      = %s
    """

    cursor.execute(query, (course_id, sec_id, semester, year))
    section_info = cursor.fetchall()
    return render_template(
        "student/section.html",
        section_info = section_info,
        course_id=course_id,
        sec_id=sec_id,
        semester=semester,
        year=year
    )

# Check advisor information
@app.route("/student-portal/advisor")
def advisor():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if session.get("role") != "student":
        return redirect("/login")
    
    STUDENT_ID = session["linked_id"]

    query = """
        SELECT i.ID, i.name, i.dept_name
        FROM advisor a
        JOIN instructor i ON a.i_ID = i.ID
        WHERE a.s_ID = %s
    """

    cursor.execute(query, (STUDENT_ID,))
    advisor_info = cursor.fetchone()
    return render_template("student/advisor.html", advisor=advisor_info)

# Registration portal
@app.route("/student-portal/register")
def register():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if session.get("role") != "student":
        return redirect("/login")
    # List classes
    # Must join with instructor,
    # Building

    query = """
        SELECT * FROM section WHERE semester = 'Spring' and year = 2022
    """

    cursor.execute(query)
    courses = cursor.fetchall()

    # Add button
    return render_template("student/register.html", 
                           courses=courses)

# Route to actually perform the class add from given url parameters
@app.route("/student-portal/register/add")
def add():
    course_id = request.args.get("course_id")
    sec_id    = request.args.get("sec_id")
    semester  = request.args.get("semester")
    year      = request.args.get("year")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if session.get("role") != "student":
        return redirect("/login")
    
    STUDENT_ID = session["linked_id"]

    query = """
        SELECT *
        FROM takes
        WHERE ID = %s
        AND course_id = %s
        AND sec_id = %s
        AND semester = %s
        AND year = %s
    """

    cursor.execute(query, (STUDENT_ID, course_id, sec_id, semester, year))
    exists = cursor.fetchone()

    if exists:
        return render_template(
            "message.html",
            message="Error: Already registered for this course",
            category="error",
            redirect_url="/student-portal/register"
        )
    
    insert_query = """
        INSERT INTO takes (ID, course_id, sec_id, semester, year)
        VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(insert_query, (STUDENT_ID, course_id, sec_id, semester, year))
    db.commit()

    return render_template(
            "message.html",
            message="Registration success!",
            category="error",
            redirect_url="/student-portal/register"
        )

# Drop portal
@app.route("/student-portal/drop")
def drop():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if session.get("role") != "student":
        return redirect("/login")
    
    STUDENT_ID = session["linked_id"]

    query = """
        SELECT s.ID, s.name, t.course_id, t.semester, t.year, t.sec_id, t.grade
        FROM student s
        JOIN takes t ON s.ID = t.ID
        WHERE s.ID = %s
    """

    cursor.execute(query, (STUDENT_ID,))
    active_courses = cursor.fetchall()

    return render_template("student/drop.html", courses=active_courses)

# Route to actually perform the drop from given url parameters
@app.route("/student-portal/drop/remove")
def remove():
    course_id = request.args.get("course_id")
    sec_id    = request.args.get("sec_id")
    semester  = request.args.get("semester")
    year      = request.args.get("year")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if session.get("role") != "student":
        return redirect("/login")
    
    STUDENT_ID = session["linked_id"]

    query = """
        SELECT *
        FROM takes
        WHERE ID = %s
        AND course_id = %s
        AND sec_id = %s
        AND semester = %s
        AND year = %s
    """

    cursor.execute(query, (STUDENT_ID, course_id, sec_id, semester, year))
    exists = cursor.fetchone()

    if not exists:
        return render_template(
            "message.html",
            message="Error: Not registered for this course!",
            category="error",
            redirect_url="/student-portal/drop"
        )
    
    delete_query = """
        DELETE FROM takes
        WHERE ID = %s
        AND course_id = %s
        AND sec_id = %s
        AND semester = %s
        AND year = %s
    """
    cursor.execute(delete_query, (STUDENT_ID, course_id, sec_id, semester, year))
    db.commit()

    return render_template(
            "message.html",
            message="Drop course success!",
            category="error",
            redirect_url="/student-portal/drop"
        )


# Allow update: Major (pick from list of choices)
# Allow name change
@app.route("/student-portal/update-info", methods=["GET", "POST"])
def update_info():
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if session.get("role") != "student":
        return redirect("/login")
    
    STUDENT_ID = session["linked_id"]

    cursor.execute("""
        SELECT ID, name, dept_name 
        FROM student
        WHERE ID = %s
    """, (STUDENT_ID,))
    student = cursor.fetchone()

    cursor.execute("SELECT dept_name FROM department ORDER BY dept_name;")
    departments = cursor.fetchall()

    if request.method == "POST":
        new_name = request.form.get("name")
        new_major = request.form.get("dept_name")

        update_query = """
            UPDATE student
            SET name = %s, dept_name = %s
            WHERE ID = %s
        """
        cursor.execute(update_query, (new_name, new_major, STUDENT_ID))
        db.commit()

        return render_template(
            "student/update_success.html",
            name=new_name,
            major=new_major
        )

    return render_template(
        "student/update_info.html",
        student=student,
        departments=departments
    )


################### ADMIN

# --------- Course CRUD

@app.route("/admin/course")
def admin_course_home():
    return render_template("admin/course_home.html")


@app.route("/admin/course/list")
def admin_course_list():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM course ORDER BY course_id;")
    courses = cursor.fetchall()

    return render_template("admin/course_list.html", courses=courses)


@app.route("/admin/course/create", methods=["GET", "POST"])
def admin_course_create():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        course_id = request.form["course_id"]
        title = request.form["title"]
        dept_name = request.form["dept_name"]
        credits = request.form["credits"]

        query = """
            INSERT INTO course (course_id, title, dept_name, credits)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (course_id, title, dept_name, credits))
        db.commit()

        return "Course created successfully!"

    cursor.execute("SELECT dept_name FROM department ORDER BY dept_name;")
    departments = cursor.fetchall()

    return render_template("admin/course_create.html", departments=departments)


@app.route("/admin/course/update", methods=["GET", "POST"])
def admin_course_update():
    course_id = request.args.get("id")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM course WHERE course_id = %s", (course_id,))
    course = cursor.fetchone()

    if not course:
        return "Course not found."

    if request.method == "POST":
        title = request.form["title"]
        dept_name = request.form["dept_name"]
        credits = request.form["credits"]

        query = """
            UPDATE course
            SET title = %s, dept_name = %s, credits = %s
            WHERE course_id = %s
        """
        cursor.execute(query, (title, dept_name, credits, course_id))
        db.commit()

        return "Course updated successfully!"

    cursor.execute("SELECT dept_name FROM department ORDER BY dept_name;")
    departments = cursor.fetchall()

    return render_template("admin/course_update.html", course=course, departments=departments)


@app.route("/admin/course/delete")
def admin_course_delete():
    course_id = request.args.get("id")
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM course WHERE course_id = %s", (course_id,))
    db.commit()

    return "Course deleted."

# --------- Section CRUD

@app.route("/admin/section")
def admin_section_home():
    return render_template("admin/section_home.html")

@app.route("/admin/section/list")
def admin_section_list():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM section ORDER BY course_id;")
    sections = cursor.fetchall()

    return render_template("admin/section_list.html", sections=sections)

@app.route("/admin/section/create", methods=["GET", "POST"])
def admin_section_create():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        course_id    = request.form["course_id"]
        sec_id       = request.form["sec_id"]
        semester     = request.form["semester"]
        year         = request.form["year"]
        building     = request.form["building"]
        room_number  = request.form["room_number"]
        time_slot_id = request.form["time_slot_id"]

        query = """
            INSERT INTO section (course_id, sec_id, semester, year, building, room_number, time_slot_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (course_id, sec_id, semester, year, building, room_number, time_slot_id))
        db.commit()

        return "Section created successfully!"


    return render_template("admin/section_create.html")

@app.route("/admin/section/update", methods=["GET", "POST"])
def admin_section_update():
    course_id = request.args.get("course_id")
    sec_id = request.args.get("sec_id")
    semester = request.args.get("semester")
    year = request.args.get("year")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    select_query = """
        SELECT * FROM section
        WHERE course_id = %s
        AND sec_id = %s
        AND semester = %s
        AND year = %s
    """
    cursor.execute(select_query, (course_id, sec_id, semester, year))
    section = cursor.fetchone()
    if not section:
        return "Section not found."

    if request.method == "POST":
        new_course_id    = request.form["course_id"]
        new_sec_id       = request.form["sec_id"]
        new_semester     = request.form["semester"]
        new_year         = request.form["year"]
        building         = request.form["building"]
        room_number      = request.form["room_number"]
        time_slot_id     = request.form["time_slot_id"]

        update_query = """
            UPDATE section
            SET course_id = %s,
                sec_id = %s,
                semester = %s,
                year = %s,
                building = %s,
                room_number = %s,
                time_slot_id = %s
            WHERE course_id = %s
                AND sec_id = %s
                AND semester = %s
                AND year = %s
        """

        cursor.execute(update_query, (
            new_course_id, new_sec_id, new_semester, new_year,
            building, room_number, time_slot_id,
            course_id, sec_id, semester, year
        ))
        db.commit()

        return "Section updated successfully!"

    return render_template("admin/section_update.html", section=section)

@app.route("/admin/section/delete")
def admin_section_delete():
    course_id = request.args.get("course_id")
    sec_id = request.args.get("sec_id")
    semester = request.args.get("semester")
    year = request.args.get("year")
    db = get_db()
    cursor = db.cursor()

    delete_query = """
        DELETE FROM section WHERE course_id = %s
        AND sec_id = %s
        AND semester = %s
        AND year = %s
    """
    cursor.execute(delete_query, (course_id, sec_id, semester, year))
    db.commit()

    return "Section deleted."


# --------- Classroom CRUD

@app.route("/admin/classroom")
def admin_classroom_home():
    return render_template("admin/classroom_home.html")

@app.route("/admin/classroom/list")
def admin_classroom_list():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM classroom ORDER BY building;")
    classrooms = cursor.fetchall()

    return render_template("admin/classroom_list.html", classrooms=classrooms)

@app.route("/admin/classroom/create", methods=["GET", "POST"])
def admin_classroom_create():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        building    = request.form["building"]
        room_number = request.form["room_number"]
        capacity     = request.form["capacity"]

        query = """
            INSERT INTO classroom (building, room_number, capacity)
            VALUES (%s, %s, %s)
        """
        cursor.execute(query, (building, room_number, capacity))
        db.commit()

        return "Classroom created successfully!"


    return render_template("admin/classroom_create.html")

@app.route("/admin/classroom/update", methods=["GET", "POST"])
def admin_classroom_update():
    building = request.args.get("building")
    room_number = request.args.get("room_number")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    select_query = """
        SELECT * FROM classroom
        WHERE building = %s
        AND room_number = %s
    """
    cursor.execute(select_query, (building, room_number))
    classroom = cursor.fetchone()
    if not classroom:
        return "Classroom not found."

    if request.method == "POST":
        new_building    = request.form["building"]
        new_room_number = request.form["room_number"]
        capacity     = request.form["capacity"]

        update_query = """
            UPDATE classroom
            SET building = %s,
                room_number = %s,
                capacity = %s
            WHERE building = %s
                AND room_number = %s
        """

        cursor.execute(update_query, (
            new_building, new_room_number, capacity, building, room_number
        ))
        db.commit()

        return "Classroom updated successfully!"

    return render_template("admin/classroom_update.html", classroom=classroom)

@app.route("/admin/classroom/delete")
def admin_classroom_delete():
    building = request.args.get("building")
    room_number = request.args.get("room_number")
    db = get_db()
    cursor = db.cursor()

    delete_query = """
        DELETE FROM classroom WHERE building = %s
        AND room_number = %s
    """
    cursor.execute(delete_query, (building, room_number))
    db.commit()

    return "Classroom deleted."


# --------- Department CRUD

@app.route("/admin/department")
def admin_department_home():
    return render_template("admin/department_home.html")

@app.route("/admin/department/list")
def admin_department_list():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM department ORDER BY budget;")
    departments = cursor.fetchall()

    return render_template("admin/department_list.html", departments=departments)

@app.route("/admin/department/create", methods=["GET", "POST"])
def admin_department_create():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        dept_name    = request.form["dept_name"]
        building     = request.form["building"]
        budget       = request.form["budget"]

        query = """
            INSERT INTO department (dept_name, building, budget)
            VALUES (%s, %s, %s)
        """
        cursor.execute(query, (dept_name, building, budget))
        db.commit()

        return "Department created successfully!"


    return render_template("admin/department_create.html")

@app.route("/admin/department/update", methods=["GET", "POST"])
def admin_department_update():
    dept_name = request.args.get("dept_name")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    select_query = """
        SELECT * FROM department
        WHERE dept_name = %s
    """
    cursor.execute(select_query, (dept_name,))
    department = cursor.fetchone()
    if not department:
        return "Department not found."

    if request.method == "POST":
        new_dept_name    = request.form["dept_name"]
        building   = request.form["building"]
        budget     = request.form["budget"]

        update_query = """
            UPDATE department
            SET dept_name = %s,
                building = %s,
                budget = %s
            WHERE dept_name = %s
        """

        cursor.execute(update_query, (
            new_dept_name, building, budget, dept_name
        ))
        db.commit()

        return "Department updated successfully!"

    return render_template("admin/department_update.html", department=department)

@app.route("/admin/department/delete")
def admin_department_delete():
    dept_name = request.args.get("dept_name")
    db = get_db()
    cursor = db.cursor()

    delete_query = """
        DELETE FROM department WHERE dept_name = %s
    """
    cursor.execute(delete_query, (dept_name,))
    db.commit()

    return "Department deleted."

# --------- Time Slot CRUD

@app.route("/admin/time_slot")
def admin_time_slot_home():
    return render_template("admin/time_slot_home.html")

@app.route("/admin/time_slot/list")
def admin_time_slot_list():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM time_slot ORDER BY start_hr;")
    time_slots = cursor.fetchall()

    return render_template("admin/time_slot_list.html", time_slots=time_slots)

@app.route("/admin/time_slot/create", methods=["GET", "POST"])
def admin_time_slot_create():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        time_slot_id    = request.form["time_slot_id"]
        day             = request.form["day"]
        start_hr        = request.form["start_hr"]
        start_min       = request.form["start_min"]
        end_hr          = request.form["end_hr"]
        end_min         = request.form["end_min"]

        query = """
            INSERT INTO time_slot (time_slot_id, day, start_hr, start_min, end_hr, end_min)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (time_slot_id, day, start_hr, start_min, end_hr, end_min))
        db.commit()

        return "Time Slot created successfully!"


    return render_template("admin/time_slot_create.html")


@app.route("/admin/time_slot/update", methods=["GET", "POST"])
def admin_time_slot_update():
    time_slot_id = request.args.get("time_slot_id")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    select_query = """
        SELECT * FROM time_slot
        WHERE time_slot_id = %s
    """
    cursor.execute(select_query, (time_slot_id,))
    time_slot = cursor.fetchone()
    if not time_slot:
        return "Time Slot not found."

    if request.method == "POST":
        new_time_slot_id    = request.form["time_slot_id"]
        day   = request.form["day"]
        start_hr     = request.form["start_hr"]
        start_min     = request.form["start_min"]
        end_hr     = request.form["end_hr"]
        end_min     = request.form["end_min"]

        update_query = """
            UPDATE time_slot
            SET time_slot_id = %s,
                day = %s,
                start_hr = %s,
                start_min = %s,
                end_hr = %s,
                end_min = %s
            WHERE time_slot_id = %s
        """

        cursor.execute(update_query, (
            new_time_slot_id, day, start_hr, start_min, end_hr, end_min, time_slot_id
        ))
        db.commit()

        return "Time Slot updated successfully!"

    return render_template("admin/time_slot_update.html", time_slot=time_slot)

@app.route("/admin/time_slot/delete")
def admin_time_slot_delete():
    time_slot_id = request.args.get("time_slot_id")
    db = get_db()
    cursor = db.cursor()

    delete_query = """
        DELETE FROM time_slot WHERE time_slot_id = %s
    """
    cursor.execute(delete_query, (time_slot_id,))
    db.commit()

    return "Time Slot deleted."


# --------- Instructor CRUD






# Test route to ensure local connection is working
@app.route("/testdb")
def testdb():
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM student LIMIT 5;")
    rows = cursor.fetchall()

    return str(rows)

if __name__ == "__main__":
    app.run(debug=True)