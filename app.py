from flask import Flask, render_template, request, redirect, session, url_for
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

SEMESTER_ORDER = {
    "Winter": 1,
    "Spring": 2,
    "Summer": 3,
    "Fall": 4
}


# TODO:
#  More checks to prevent incomplete/error queries (deleting department with instructors in it)

# Login setup instructions
# Create users table
# Insert a few users with either role 'student' 'admin' or 'instructor' and password



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
            return redirect("/admin-portal")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

################### INSTRUCTOR

#instructor portal
@app.route("/instructor-portal")
def instructor_portal():
    if session.get("role") != "instructor":
        return redirect("/login")
    
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    instructor_id = session["linked_id"]

    cursor.execute("""
        SELECT ID, name 
        FROM instructor
        WHERE ID = %s
    """, (instructor_id,))
    instructor = cursor.fetchone()
    
    return render_template("instructor/instructor_portal.html", instructor=instructor)

#update information
@app.route("/instructor-portal/update-info", methods=["GET", "POST"])
def update_info_instructor():
    if session.get("role") != "instructor":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    instructor_id = session.get("linked_id")

    cursor.execute("""
        SELECT ID, name, dept_name
        FROM instructor
        WHERE ID = %s
    """, (instructor_id,))
    instructor = cursor.fetchone()

    cursor.execute("SELECT dept_name FROM department ORDER BY dept_name;")
    departments = cursor.fetchall()

    if request.method == "POST":
        new_name = request.form.get("name")
        new_dept = request.form.get("dept_name")

        update_query = """
            UPDATE instructor
            SET name = %s, dept_name = %s
            WHERE ID = %s
        """
        cursor.execute(update_query, (new_name, new_dept, instructor_id))
        db.commit()

        return render_template("instructor/update_success.html",
                               name=new_name, dept=new_dept)

    return render_template("instructor/update_info.html",
                           instructor=instructor, departments=departments)


# View advised students
@app.route("/instructor-portal/advising", methods=["GET"])
def instructor_advising():
    if session.get("role") != "instructor":
        return redirect("/login")

    instructor_id = session.get("linked_id")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.ID, s.name
        FROM student s
        JOIN advisor a ON s.ID = a.s_id
        WHERE a.i_id = %s
    """, (instructor_id,))
    advisees = cursor.fetchall()

    cursor.execute("""
        SELECT ID, name
        FROM student
        WHERE ID NOT IN (SELECT s_id FROM advisor)
    """)
    unassigned_students = cursor.fetchall()

    return render_template("instructor/advising.html",
                           advisees=advisees,
                           unassigned_students=unassigned_students)


# Add advised student
@app.route("/instructor-portal/advising/add", methods=["POST"])
def add_advisee():
    if session.get("role") != "instructor":
        return redirect("/login")

    instructor_id = session.get("linked_id")
    student_id = request.form.get("student_id")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM student WHERE ID = %s", (student_id,))
    student = cursor.fetchone()
    if not student:
        return "Student ID not found!"

    cursor.execute("SELECT * FROM advisor WHERE s_id = %s", (student_id,))
    if cursor.fetchone():
        return "This student already has an advisor."

    cursor.execute("INSERT INTO advisor (s_id, i_id) VALUES (%s, %s)", (student_id, instructor_id))
    db.commit()

    return redirect("/instructor-portal/advising")


# Remove advised student
@app.route("/instructor-portal/advising/remove", methods=["POST"])
def remove_advisee():
    if session.get("role") != "instructor":
        return redirect("/login")

    instructor_id = session.get("linked_id")
    student_id = request.form.get("student_id")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("DELETE FROM advisor WHERE s_id = %s AND i_id = %s", (student_id, instructor_id))
    db.commit()

    return redirect("/instructor-portal/advising")

# View and submit/change grades
@app.route("/instructor-portal/grades", methods=["GET", "POST"])
def instructor_grades():
    if session.get("role") != "instructor":
        return redirect("/login")

    instructor_id = session.get("linked_id")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT s.course_id, s.sec_id, s.semester, s.year, c.title
        FROM teaches t
        JOIN section s ON t.course_id = s.course_id AND t.sec_id = s.sec_id
                     AND t.semester = s.semester AND t.year = s.year
        JOIN course c ON s.course_id = c.course_id
        WHERE t.ID = %s
    """, (instructor_id,))
    sections = cursor.fetchall()

    selected_section = request.form.get("section") or None
    students = []

    if selected_section:
        course_id, sec_id, semester, year = selected_section.split(",")
        cursor.execute("""
            SELECT st.ID, st.name, tk.grade
            FROM takes tk
            JOIN student st ON tk.ID = st.ID
            WHERE tk.course_id = %s AND tk.sec_id = %s
              AND tk.semester = %s AND tk.year = %s
        """, (course_id, sec_id, semester, year))
        students = cursor.fetchall()

    if request.method == "POST" and request.form.get("update_grades"):
        for student in students:
            grade = request.form.get(f"grade_{student['ID']}")
            cursor.execute("""
                UPDATE takes
                SET grade = %s
                WHERE ID = %s AND course_id = %s AND sec_id = %s
                  AND semester = %s AND year = %s
            """, (grade, student['ID'], course_id, sec_id, semester, year))
        db.commit()
        return redirect("/instructor-portal/grades")

    return render_template("instructor/grades.html",
                           sections=sections,
                           students=students,
                           selected_section=selected_section)

#Modify Prereqs
@app.route("/instructor-portal/prereq", methods=["GET", "POST"])
def view_prereq():
    if session.get("role") != "instructor":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    instructor_id = session.get("linked_id")
    cursor.execute("SELECT course_id, title FROM course WHERE dept_name IN (SELECT dept_name FROM instructor WHERE ID = %s)", (instructor_id,))
    courses = cursor.fetchall()

    selected_course = None
    prereqs = []

    course_id = request.args.get("course_id")
    if request.method == "POST":
        course_id = request.form.get("course_id")

    if course_id:
        selected_course = next((c for c in courses if c["course_id"] == course_id), None)
        cursor.execute("SELECT prereq_id FROM prereq WHERE course_id = %s", (course_id,))
        prereqs = cursor.fetchall()

    cursor.execute("SELECT course_id, title FROM course")
    all_courses = cursor.fetchall()

    return render_template("instructor/prereq.html",
                           courses=courses,
                           selected_course=selected_course,
                           prereqs=prereqs,
                           all_courses=all_courses)
@app.route("/instructor-portal/prereq/add", methods=["POST"])
def add_prereq():
    if session.get("role") != "instructor":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor()

    course_id = request.form["course_id"]
    prereq_id = request.form["prereq_id"]

    cursor.execute("INSERT INTO prereq (course_id, prereq_id) VALUES (%s, %s)", (course_id, prereq_id))
    db.commit()

    return redirect(f"/instructor-portal/prereq?course_id={course_id}")

#remove prereq
@app.route("/instructor-portal/prereq/remove", methods=["POST"])
def remove_prereq():
    if session.get("role") != "instructor":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor()

    course_id = request.form["course_id"]
    prereq_id = request.form["prereq_id"]

    cursor.execute("DELETE FROM prereq WHERE course_id = %s AND prereq_id = %s", (course_id, prereq_id))
    db.commit()

    return redirect(f"/instructor-portal/prereq?course_id={course_id}")

# View sections and roster
@app.route("/instructor-portal/section", methods=["GET", "POST"])
def view_sections():
    if session.get("role") != "instructor":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    instructor_id = session.get("linked_id")

    semesters = ["Fall", "Winter", "Spring", "Summer"]
    selected_semester = None
    sections = []
    selected_section = None
    roster = []

    if request.method == "POST" and "semester" in request.form:
        selected_semester = request.form["semester"]
        cursor.execute("""
            SELECT course_id, sec_id, semester, year
            FROM teaches
            WHERE ID=%s AND semester=%s
        """, (instructor_id, selected_semester))
        sections = cursor.fetchall()

    if request.method == "POST" and "section_id" in request.form:
        vals = request.form["section_id"].split("|")
        course_id, sec_id, semester, year = vals
        selected_section = {
            "course_id": course_id,
            "sec_id": sec_id,
            "semester": semester,
            "year": int(year)
        }

        cursor.execute("""
            SELECT s.ID, s.name
            FROM student s
            JOIN takes t ON s.ID = t.ID
            WHERE t.course_id=%s AND t.sec_id=%s AND t.semester=%s AND t.year=%s
        """, (course_id, sec_id, semester, year))
        roster = cursor.fetchall()

        selected_semester = semester
        cursor.execute("""
            SELECT course_id, sec_id, semester, year
            FROM teaches
            WHERE ID=%s AND semester=%s
        """, (instructor_id, selected_semester))
        sections = cursor.fetchall()

    return render_template("instructor/section.html",
                           semesters=semesters,
                           selected_semester=selected_semester,
                           sections=sections,
                           selected_section=selected_section,
                           roster=roster)

#remove student from section
@app.route("/instructor-portal/section/remove", methods=["POST"])
def remove_student():
    if session.get("role") != "instructor":
        return redirect("/login")
    
    db = get_db()
    cursor = db.cursor()
    instructor_id = session.get("linked_id")

    course_id = request.form.get("course_id")
    sec_id = request.form.get("sec_id")
    semester = request.form.get("semester")
    year = request.form.get("year")
    student_id = request.form.get("student_id")

    # Optional: Verify the instructor actually teaches this section
    cursor.execute("""
        SELECT * FROM teaches
        WHERE ID=%s AND course_id=%s AND sec_id=%s AND semester=%s AND year=%s
    """, (instructor_id, course_id, sec_id, semester, year))
    teaches = cursor.fetchone()
    if not teaches:
        return "You are not authorized to modify this section.", 403

    # Remove student from takes table
    cursor.execute("""
        DELETE FROM takes
        WHERE ID=%s AND course_id=%s AND sec_id=%s AND semester=%s AND year=%s
    """, (student_id, course_id, sec_id, semester, year))
    db.commit()

    return redirect("/instructor-portal/section")

# Average grade of all students based on department
@app.route("/instructor-portal/department-averages", methods=["GET", "POST"])
def department_averages():
    if session.get("role") != "instructor":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    query = """
        SELECT d.dept_name,
            AVG(
                CASE t.grade
                    WHEN 'A' THEN 4
                    WHEN 'B' THEN 3
                    WHEN 'C' THEN 2
                    WHEN 'D' THEN 1
                    WHEN 'F' THEN 0
                END
            ) AS avg_gpa
        FROM takes t
        JOIN student s on t.ID = s.ID
        JOIN department d on s.dept_name = d.dept_name
        GROUP BY d.dept_name;
    """

    cursor.execute(query)
    dept_averages = cursor.fetchall()
    return render_template("instructor/department_averages.html", dept_averages=dept_averages)


# Average grade of class across a range of semesters
@app.route("/instructor-portal/class-averages", methods=["GET", "POST"] )
def class_averages():
    if session.get("role") != "instructor":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    instructor_id = session.get("linked_id")

    cursor.execute("""
        SELECT DISTINCT c.course_id, c.title
        FROM teaches t
        JOIN course c ON t.course_id = c.course_id
        WHERE t.ID = %s
    """, (instructor_id,))
    courses = cursor.fetchall()
    results = None

    if request.method == "POST":
        course_id = request.form.get("course_id")
        start_sem = request.form.get("start_sem")
        start_year = int(request.form.get("start_year"))
        end_sem = request.form.get("end_sem")
        end_year = int(request.form.get("end_year"))
        start_val = start_year * 10 + SEMESTER_ORDER[start_sem]
        end_val = end_year * 10 + SEMESTER_ORDER[end_sem]

        # Multiply year values by 10 for easier ordering
        query = """
            SELECT 
                AVG(
                    CASE 
                        WHEN grade='A' THEN 4.0
                        WHEN grade='B' THEN 3.0
                        WHEN grade='C' THEN 2.0
                        WHEN grade='D' THEN 1.0
                        WHEN grade='F' THEN 0.0
                        ELSE NULL
                    END
                ) AS avg_grade
            FROM takes tk
            JOIN teaches t ON tk.course_id = t.course_id 
                           AND tk.sec_id = t.sec_id
                           AND tk.semester = t.semester
                           AND tk.year = t.year
            WHERE t.ID = %s
              AND tk.course_id = %s
              AND (tk.year * 10 + 
                   CASE tk.semester
                       WHEN 'Spring' THEN 1
                       WHEN 'Summer' THEN 2
                       WHEN 'Fall' THEN 3
                       WHEN 'Winter' THEN 4
                   END)
                  BETWEEN %s AND %s
        """

        cursor.execute(query, (instructor_id, course_id, start_val, end_val))
        results = cursor.fetchone()
    return render_template("instructor/class_averages.html",
                           courses=courses,
                           results=results)


@app.route("/instructor/best-worst-class", methods=["GET", "POST"])
def best_worst_class():
    if session.get("role") != "instructor":
        return redirect("/login")

    results = []
    if request.method == "POST":
        semester = request.form.get("semester")
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT course_id, AVG(grade) AS avg_grade
            FROM takes
            WHERE semester = %s
            GROUP BY course_id
            ORDER BY avg_grade DESC
        """, (semester,))
        results = cursor.fetchall()

    return render_template("instructor/best_worst_class.html", results=results)

@app.route("/instructor/total-students")
def total_students():
    if session.get("role") != "instructor":
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.dept_name, COUNT(DISTINCT s.ID) AS total_students
        FROM student s
        GROUP BY s.dept_name
    """)
    results = cursor.fetchall()
    return render_template("instructor/total_students.html", results=results)

@app.route("/instructor/current-students", methods=["GET", "POST"])
def current_students():
    if session.get("role") != "instructor":
        return redirect("/login")

    results = []
    if request.method == "POST":
        semester = request.form.get("semester")
        db = get_db()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.dept_name, COUNT(DISTINCT t.ID) AS current_students
            FROM student s
            JOIN takes t ON s.ID = t.ID
            JOIN section sec ON t.course_id = sec.course_id AND t.sec_id = sec.sec_id
            WHERE t.semester = %s
            GROUP BY s.dept_name
        """, (semester,))
        results = cursor.fetchall()

    return render_template("instructor/current_students.html", results=results)








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

    return render_template("student/student_portal.html", student=student, year = CURRENT_YEAR, semester = CURRENT_SEMESTER)


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
@app.route("/student-portal/courses", methods=["GET", "POST"])
def courses():
    selected_semester = request.form.get("semester")
    db = get_db()
    cursor = db.cursor(dictionary=True)
    if session.get("role") != "student":
        return redirect("/login")
    
    STUDENT_ID = session["linked_id"]

    query = """
        SELECT s.ID, s.name, t.course_id, c.title, 
            t.semester, t.year, t.sec_id, t.grade
        FROM student s
        JOIN takes t ON s.ID = t.ID
        JOIN course c ON t.course_id = c.course_id
        WHERE s.ID = %s
    """

    params = [STUDENT_ID]

    if selected_semester and selected_semester != "all":
        query += " AND t.semester = %s"
        params.append(selected_semester)

    cursor.execute(query, params)
    semester_rows = cursor.fetchall()

    for row in semester_rows:
        course_year = row["year"]
        course_sem = row["semester"]

        if course_year == CURRENT_YEAR and course_sem == CURRENT_SEMESTER:
            row["status"] = "Active"

        elif course_year > CURRENT_YEAR or (course_year == CURRENT_YEAR and SEMESTER_ORDER[course_sem] > SEMESTER_ORDER[CURRENT_SEMESTER]):
            row["status"] = "Upcoming"
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

    query = """
        SELECT * FROM section WHERE semester = 'Spring' and year = 2022
    """

    cursor.execute(query)
    courses = cursor.fetchall()

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

@app.route("/admin-portal")
def admin_portal():
    if session.get("role") != "admin":
        return redirect("/login")

    return render_template("admin/admin_portal.html")



# --------- Course CRUD

@app.route("/admin/course")
def admin_course_home():
    if session.get("role") != "admin":
        return redirect("/login")
    return render_template("admin/course_home.html")


@app.route("/admin/course/list")
def admin_course_list():
    if session.get("role") != "admin":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM course ORDER BY course_id;")
    courses = cursor.fetchall()

    return render_template("admin/course_list.html", courses=courses)


@app.route("/admin/course/create", methods=["GET", "POST"])
def admin_course_create():
    if session.get("role") != "admin":
        return redirect("/login")
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
    if session.get("role") != "admin":
        return redirect("/login")
    course_id = request.args.get("id")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM course WHERE course_id = %s", (course_id,))
    course = cursor.fetchone()

    if not course:
        return render_template(
            "message.html",
            message="Error: Course not found",
            category="error",
            redirect_url="/student-portal/register"
        )

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

        return render_template(
            "message.html",
            message="Course updated successfully!",
            category="error",
            redirect_url="/student-portal/register"
        )

    cursor.execute("SELECT dept_name FROM department ORDER BY dept_name;")
    departments = cursor.fetchall()

    return render_template("admin/course_update.html", course=course, departments=departments)


@app.route("/admin/course/delete")
def admin_course_delete():
    if session.get("role") != "admin":
        return redirect("/login")
    course_id = request.args.get("id")
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM course WHERE course_id = %s", (course_id,))
    db.commit()

    return render_template(
            "message.html",
            message="Error: Course deleted",
            category="error",
            redirect_url="/student-portal/register"
        )


# --------- Section CRUD

@app.route("/admin/section")
def admin_section_home():
    if session.get("role") != "admin":
        return redirect("/login")
    return render_template("admin/section_home.html")

@app.route("/admin/section/list")
def admin_section_list():
    if session.get("role") != "admin":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM section ORDER BY course_id;")
    sections = cursor.fetchall()

    return render_template("admin/section_list.html", sections=sections)

@app.route("/admin/section/create", methods=["GET", "POST"])
def admin_section_create():
    if session.get("role") != "admin":
        return redirect("/login")
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
    if session.get("role") != "admin":
        return redirect("/login")
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
        return render_template(
            "message.html",
            message="Error: Section not found.",
            category="error",
            redirect_url="/student-portal/register"
        )

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

        return render_template(
            "message.html",
            message="Section updated successfully.",
            category="error",
            redirect_url="/admin/section"
        )

    return render_template("admin/section_update.html", section=section)

@app.route("/admin/section/delete")
def admin_section_delete():
    if session.get("role") != "admin":
        return redirect("/login")
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

    return render_template(
            "message.html",
            message="Section deleted successfully.",
            category="error",
            redirect_url="/admin/section"
        )


# --------- Classroom CRUD

@app.route("/admin/classroom")
def admin_classroom_home():
    if session.get("role") != "admin":
        return redirect("/login")
    return render_template("admin/classroom_home.html")

@app.route("/admin/classroom/list")
def admin_classroom_list():
    if session.get("role") != "admin":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM classroom ORDER BY building;")
    classrooms = cursor.fetchall()

    return render_template("admin/classroom_list.html", classrooms=classrooms)

@app.route("/admin/classroom/create", methods=["GET", "POST"])
def admin_classroom_create():
    if session.get("role") != "admin":
        return redirect("/login")
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
    if session.get("role") != "admin":
        return redirect("/login")
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
    if session.get("role") != "admin":
        return redirect("/login")
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

    return render_template(
            "message.html",
            message="Classroom deleted successfully.",
            category="error",
            redirect_url="/admin/classroom"
        )


# --------- Department CRUD

@app.route("/admin/department")
def admin_department_home():
    if session.get("role") != "admin":
        return redirect("/login")
    return render_template("admin/department_home.html")

@app.route("/admin/department/list")
def admin_department_list():
    if session.get("role") != "admin":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM department ORDER BY budget;")
    departments = cursor.fetchall()

    return render_template("admin/department_list.html", departments=departments)

@app.route("/admin/department/create", methods=["GET", "POST"])
def admin_department_create():
    if session.get("role") != "admin":
        return redirect("/login")
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

        return render_template(
            "message.html",
            message="Department created successfully.",
            category="error",
            redirect_url="/admin/department"
        )


    return render_template("admin/department_create.html")

@app.route("/admin/department/update", methods=["GET", "POST"])
def admin_department_update():
    if session.get("role") != "admin":
        return redirect("/login")
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
        return render_template(
            "message.html",
            message="Error: Department not found.",
            category="error",
            redirect_url="/admin/department"
        )

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

        return render_template(
            "message.html",
            message="Department updated successfully.",
            category="error",
            redirect_url="/admin/department"
        )

    return render_template("admin/department_update.html", department=department)

@app.route("/admin/department/delete")
def admin_department_delete():
    if session.get("role") != "admin":
        return redirect("/login")
    dept_name = request.args.get("dept_name")
    db = get_db()
    cursor = db.cursor()

    delete_query = """
        DELETE FROM department WHERE dept_name = %s
    """
    cursor.execute(delete_query, (dept_name,))
    db.commit()

    return render_template(
            "message.html",
            message="Department deleted successfully.",
            category="error",
            redirect_url="/admin/department"
        )

# --------- Time Slot CRUD

@app.route("/admin/time_slot")
def admin_time_slot_home():
    if session.get("role") != "admin":
        return redirect("/login")
    return render_template("admin/time_slot_home.html")

@app.route("/admin/time_slot/list")
def admin_time_slot_list():
    if session.get("role") != "admin":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM time_slot ORDER BY start_hr;")
    time_slots = cursor.fetchall()

    return render_template("admin/time_slot_list.html", time_slots=time_slots)

@app.route("/admin/time_slot/create", methods=["GET", "POST"])
def admin_time_slot_create():
    if session.get("role") != "admin":
        return redirect("/login")
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

        return render_template(
            "message.html",
            message="Time Slot created successfully.",
            category="error",
            redirect_url="/admin/time_slot"
        )


    return render_template("admin/time_slot_create.html")


@app.route("/admin/time_slot/update", methods=["GET", "POST"])
def admin_time_slot_update():
    if session.get("role") != "admin":
        return redirect("/login")
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
        return render_template(
            "message.html",
            message="Time Slot not found.",
            category="error",
            redirect_url="/admin/time_slot"
        )

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

        return render_template(
            "message.html",
            message="Time Slot updated successfully.",
            category="error",
            redirect_url="/admin/time_slot"
        )

    return render_template("admin/time_slot_update.html", time_slot=time_slot)

@app.route("/admin/time_slot/delete")
def admin_time_slot_delete():
    if session.get("role") != "admin":
        return redirect("/login")
    time_slot_id = request.args.get("time_slot_id")
    db = get_db()
    cursor = db.cursor()

    delete_query = """
        DELETE FROM time_slot WHERE time_slot_id = %s
    """
    cursor.execute(delete_query, (time_slot_id,))
    db.commit()

    return render_template(
            "message.html",
            message="Time Slot deleted successfully.",
            category="error",
            redirect_url="/admin/time_slot"
        )


# --------- Instructor CRUD

@app.route("/admin/instructor")
def admin_instructor_home():
    if session.get("role") != "admin":
        return redirect("/login")
    return render_template("admin/instructor_home.html")


@app.route("/admin/instructor/list")
def admin_instructor_list():
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM instructor")
    instructors = cursor.fetchall()

    return render_template("admin/instructor_list.html", instructors=instructors)


@app.route("/admin/instructor/create", methods=["GET", "POST"])
def admin_instructor_create():
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()
    cursor = db.cursor()

    if request.method == "POST":
        name = request.form["name"]
        dept = request.form["dept_name"]
        salary = request.form["salary"]

        cursor.execute(
            "INSERT INTO instructor (name, dept_name, salary) VALUES (%s, %s, %s)",
            (name, dept, salary)
        )
        db.commit()

        return redirect("/admin/instructor")

    return render_template("admin/instructor_create.html")


@app.route("/admin/instructor/update", methods=["GET", "POST"])
def admin_instructor_update():
    if session.get("role") != "admin":
        return redirect("/login")

    instructor_id = request.args.get("id")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch instructor info
    cursor.execute("SELECT * FROM instructor WHERE ID = %s", (instructor_id,))
    instructor = cursor.fetchone()
    if not instructor:
        return render_template(
            "message.html",
            message="Error: Instructor not found.",
            category="error",
            redirect_url="/admin/instructor/list"
        )

    if request.method == "POST":
        name = request.form["name"]
        dept_name = request.form["dept_name"]
        salary = request.form["salary"]

        cursor.execute("""
            UPDATE instructor
            SET name = %s, dept_name = %s, salary = %s
            WHERE ID = %s
        """, (name, dept_name, salary, instructor_id))
        db.commit()

        return render_template(
            "message.html",
            message="Instructor updated successfully!",
            category="success",
            redirect_url="/admin/instructor/list"
        )

    # Fetch all departments for dropdown
    cursor.execute("SELECT dept_name FROM department ORDER BY dept_name")
    departments = cursor.fetchall()

    return render_template(
        "admin/instructor_update.html",
        instructor=instructor,
        departments=departments
    )

@app.route("/admin/instructor/delete")
def admin_instructor_delete():
    if session.get("role") != "admin":
        return redirect("/login")

    id = request.args.get("id")
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM instructor WHERE ID = %s", (id,))
    db.commit()

    return redirect("/admin/instructor/list")

# --------------- Student CRUD

# --------- Student CRUD

@app.route("/admin/student")
def admin_student_home():
    if session.get("role") != "admin":
        return redirect("/login")
    return render_template("admin/student_home.html")


@app.route("/admin/student/list")
def admin_student_list():
    if session.get("role") != "admin":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM student ORDER BY ID;")
    students = cursor.fetchall()

    return render_template("admin/student_list.html", students=students)


@app.route("/admin/student/create", methods=["GET", "POST"])
def admin_student_create():
    if session.get("role") != "admin":
        return redirect("/login")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT dept_name FROM department")
    departments = cursor.fetchall()

    if request.method == "POST":
        ID = request.form["ID"]
        name = request.form["name"]
        dept_name = request.form["dept_name"]
        tot_cred = request.form["tot_cred"]

        cursor.execute("""
            INSERT INTO student (ID, name, dept_name, tot_cred)
            VALUES (%s, %s, %s, %s)
        """, (ID, name, dept_name, tot_cred))
        db.commit()

        return render_template("message.html",
                               message="Student created successfully.",
                               category="success",
                               redirect_url="/admin/student")

    return render_template("admin/student_create.html", departments=departments)


@app.route("/admin/student/update", methods=["GET", "POST"])
def admin_student_update():
    if session.get("role") != "admin":
        return redirect("/login")

    student_id = request.args.get("ID")
    db = get_db()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM student WHERE ID = %s", (student_id,))
    student = cursor.fetchone()

    if not student:
        return render_template("message.html",
                               message="Error: Student not found.",
                               category="error",
                               redirect_url="/admin/student")

    cursor.execute("SELECT dept_name FROM department")
    departments = cursor.fetchall()

    if request.method == "POST":
        new_id = request.form["ID"]
        name = request.form["name"]
        dept_name = request.form["dept_name"]
        tot_cred = request.form["tot_cred"]

        cursor.execute("""
            UPDATE student
            SET ID=%s, name=%s, dept_name=%s, tot_cred=%s
            WHERE ID=%s
        """, (new_id, name, dept_name, tot_cred, student_id))
        db.commit()

        return render_template("message.html",
                               message="Student updated successfully.",
                               category="success",
                               redirect_url="/admin/student")

    return render_template("admin/student_update.html",
                           student=student,
                           departments=departments)


@app.route("/admin/student/delete")
def admin_student_delete():
    if session.get("role") != "admin":
        return redirect("/login")

    student_id = request.args.get("ID")
    db = get_db()
    cursor = db.cursor()

    cursor.execute("DELETE FROM student WHERE ID = %s", (student_id,))
    db.commit()

    return render_template("message.html",
                           message="Student deleted successfully.",
                           category="success",
                           redirect_url="/admin/student")

# -------- ASSIGN CRUD

@app.route("/admin/teaches")
def teaches_home():
    if session.get("role") != "admin":
        return redirect("/login")
    return render_template("admin/teaches_home.html")

@app.route("/admin/teaches/list")
def teaches_list():
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT t.course_id, t.sec_id, t.semester, t.year, t.ID, i.name AS instructor_name
        FROM teaches t
        LEFT JOIN instructor i ON t.ID = i.ID
        ORDER BY t.course_id, t.sec_id
    """)
    assignments = cursor.fetchall()
    return render_template("admin/teaches_list.html", assignments=assignments)

@app.route("/admin/teaches/create", methods=["GET", "POST"])
def teaches_create():
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True)

    # Fetch courses and instructors
    cursor.execute("SELECT course_id, title FROM course ORDER BY course_id")
    courses = cursor.fetchall()
    cursor.execute("SELECT ID, name, dept_name FROM instructor ORDER BY name")
    instructors = cursor.fetchall()

    if request.method == "POST":
        course_id = request.form.get("course_id")
        sec_id = request.form.get("sec_id")
        semester = request.form.get("semester")
        year = request.form.get("year")
        ID = request.form.get("ID")

        if ID:
            cursor.execute("""
                INSERT INTO teaches (course_id, sec_id, semester, year, ID)
                VALUES (%s, %s, %s, %s, %s)
            """, (course_id, sec_id, semester, year, ID))
            db.commit()
            return redirect("/admin/teaches/list")

    return render_template("admin/teaches_create.html", courses=courses, instructors=instructors)

@app.route("/admin/teaches/update", methods=["GET", "POST"])
def teaches_update():
    if session.get("role") != "admin":
        return redirect("/login")

    db = get_db()
    cursor = db.cursor(dictionary=True, buffered=True)  # Buffered cursor

    course_id = request.args.get("course_id")
    sec_id = request.args.get("sec_id")
    semester = request.args.get("semester")
    year = request.args.get("year")

    # Fetch courses and instructors
    cursor.execute("SELECT course_id, title FROM course ORDER BY course_id")
    courses = cursor.fetchall()

    cursor.execute("SELECT ID, name, dept_name FROM instructor ORDER BY name")
    instructors = cursor.fetchall()

    # Fetch current assignment
    cursor.execute("""
        SELECT ID FROM teaches
        WHERE course_id=%s AND sec_id=%s AND semester=%s AND year=%s
    """, (course_id, sec_id, semester, year))
    current = cursor.fetchone()
    prefill_ID = current["ID"] if current else None

    if request.method == "POST":
        new_course_id = request.form.get("course_id")
        new_sec_id = request.form.get("sec_id")
        new_semester = request.form.get("semester")
        new_year = request.form.get("year")
        ID = request.form.get("ID")

        if ID:
            # Update assignment
            cursor.execute("""
                UPDATE teaches
                SET course_id=%s, sec_id=%s, semester=%s, year=%s, ID=%s
                WHERE course_id=%s AND sec_id=%s AND semester=%s AND year=%s
            """, (new_course_id, new_sec_id, new_semester, new_year, ID,
                  course_id, sec_id, semester, year))
            db.commit()
            return redirect("/admin/teaches/list")

    return render_template("admin/teaches_update.html",
                           courses=courses,
                           instructors=instructors,
                           course_id=course_id,
                           sec_id=sec_id,
                           semester=semester,
                           year=year,
                           prefill_ID=prefill_ID)

@app.route("/admin/teaches/delete", methods=["POST"])
def teaches_delete():
    if session.get("role") != "admin":
        return redirect("/login")
    
    db = get_db()
    cursor = db.cursor()
    
    course_id = request.form.get("course_id")
    sec_id = request.form.get("sec_id")
    semester = request.form.get("semester")
    year = request.form.get("year")
    
    cursor.execute("""
        DELETE FROM teaches
        WHERE course_id=%s AND sec_id=%s AND semester=%s AND year=%s
    """, (course_id, sec_id, semester, year))
    
    db.commit()
    return redirect("/admin/teaches/list")




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