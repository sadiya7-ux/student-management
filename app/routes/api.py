import re
from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Student

api_bp = Blueprint("api", __name__, url_prefix="/api")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s()-]{6,19}$")
_ADMISSION_YEAR_RE = re.compile(r"^[0-9]{4}$")
_MIN_ADMISSION_YEAR = 1900
_MAX_YEAR_OF_STUDY = 4
_TEXT_LIMITS = {
    "full_name": 120,
    "roll_number": 40,
    "email": 254,
    "phone_number": 25,
    "department": 100,
    "course": 120,
}
_REQUIRED_FIELDS = tuple(_TEXT_LIMITS) + ("year_of_study", "date_of_admission")


def _error(message: str, status: int, details: dict | None = None):
    body = {"error": message}
    if details:
        body["details"] = details
    return jsonify(body), status


def _validate_student(payload: object, student_id: int | None = None):
    if not isinstance(payload, dict):
        return None, {"body": "Request body must be a JSON object"}

    errors = {}
    values = {}

    for field in _REQUIRED_FIELDS:
        if field not in payload or payload[field] is None or payload[field] == "":
            errors[field] = "This field is required"

    for field, limit in _TEXT_LIMITS.items():
        value = payload.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            errors[field] = "Must be text"
            continue
        value = value.strip()
        if not value:
            errors[field] = "This field cannot be blank"
        elif len(value) > limit:
            errors[field] = f"Must be {limit} characters or fewer"
        else:
            values[field] = value

    if "email" in values and not _EMAIL_RE.fullmatch(values["email"]):
        errors["email"] = "Enter a valid email address"
    if "phone_number" in values and not _PHONE_RE.fullmatch(
        values["phone_number"]
    ):
        errors["phone_number"] = "Enter a valid phone number"

    if "year_of_study" in payload:
        year = payload["year_of_study"]
        if (
            isinstance(year, bool)
            or not isinstance(year, int)
            or not 1 <= year <= _MAX_YEAR_OF_STUDY
        ):
            errors["year_of_study"] = "Enter a whole number from 1 to 4"
        else:
            values["year_of_study"] = year

    if "date_of_admission" in payload and payload["date_of_admission"] not in (
        None,
        "",
    ):
        raw_date = payload["date_of_admission"]
        current_year = date.today().year
        if not isinstance(raw_date, str) or not _ADMISSION_YEAR_RE.fullmatch(
            raw_date
        ):
            errors["date_of_admission"] = "Enter a four-digit admission year."
        else:
            admission_year = int(raw_date)
            if not _MIN_ADMISSION_YEAR <= admission_year <= current_year:
                errors["date_of_admission"] = (
                    f"Enter an admission year between {_MIN_ADMISSION_YEAR} "
                    f"and {current_year}."
                )
            else:
                values["date_of_admission"] = date(admission_year, 1, 1)

    if errors:
        return None, errors

    duplicate_checks = (
        ("roll_number", Student.roll_number),
        ("email", Student.email),
    )
    for field, column in duplicate_checks:
        existing = db.session.execute(
            select(Student.id).where(
                func.lower(column) == values[field].lower(),
                Student.id != (student_id or -1),
            )
        ).scalar_one_or_none()
        if existing is not None:
            errors[field] = (
                "A student with this roll number already exists"
                if field == "roll_number"
                else "A student with this email already exists"
            )

    return (values if not errors else None), errors


@api_bp.get("/students")
def list_students():
    query = select(Student)
    search = request.args.get("search", request.args.get("q", "")).strip()
    department = request.args.get("department", "").strip()

    if search:
        like = f"%{search}%"
        query = query.where(
            or_(Student.full_name.ilike(like), Student.roll_number.ilike(like))
        )
    if department:
        query = query.where(func.lower(Student.department) == department.lower())

    students = db.session.execute(
        query.order_by(Student.full_name.asc(), Student.id.asc())
    ).scalars()
    data = [student.to_dict() for student in students]
    return jsonify(data=data, count=len(data))


@api_bp.get("/students/<int:student_id>")
def get_student(student_id: int):
    student = db.session.get(Student, student_id)
    if student is None:
        return _error("Student not found", 404)
    return jsonify(data=student.to_dict())


@api_bp.post("/students")
def create_student():
    values, errors = _validate_student(request.get_json(silent=True))
    if errors:
        return _error("Please correct the highlighted fields", 400, errors)

    student = Student(**values)
    db.session.add(student)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("A student with this email or roll number already exists", 409)
    return jsonify(data=student.to_dict()), 201


@api_bp.put("/students/<int:student_id>")
def update_student(student_id: int):
    student = db.session.get(Student, student_id)
    if student is None:
        return _error("Student not found", 404)

    values, errors = _validate_student(request.get_json(silent=True), student_id)
    if errors:
        return _error("Please correct the highlighted fields", 400, errors)

    for field, value in values.items():
        setattr(student, field, value)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("A student with this email or roll number already exists", 409)
    return jsonify(data=student.to_dict())


@api_bp.delete("/students/<int:student_id>")
def delete_student(student_id: int):
    student = db.session.get(Student, student_id)
    if student is None:
        return _error("Student not found", 404)
    db.session.delete(student)
    db.session.commit()
    return jsonify(message="Student deleted successfully")


@api_bp.get("/dashboard/stats")
def dashboard_stats():
    total = db.session.scalar(select(func.count()).select_from(Student)) or 0
    departments = db.session.execute(
        select(Student.department, func.count(Student.id))
        .group_by(Student.department)
        .order_by(func.count(Student.id).desc(), Student.department.asc())
    ).all()
    year_counts = db.session.execute(
        select(Student.year_of_study, func.count(Student.id))
        .where(Student.year_of_study.between(1, _MAX_YEAR_OF_STUDY))
        .group_by(Student.year_of_study)
        .order_by(Student.year_of_study.asc())
    ).all()
    year_count_by_year = dict(year_counts)
    recent_students = db.session.execute(
        select(Student).order_by(Student.created_at.desc(), Student.id.desc()).limit(5)
    ).scalars()

    return jsonify(
        data={
            "total_students": total,
            "department_count": len(departments),
            "by_department": [
                {"department": name, "count": count} for name, count in departments
            ],
            "by_year": [
                {"year": year, "count": year_count_by_year.get(year, 0)}
                for year in range(1, _MAX_YEAR_OF_STUDY + 1)
            ],
            "recent_students": [student.to_dict() for student in recent_students],
        }
    )
