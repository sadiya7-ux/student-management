from datetime import datetime, timezone

from app.extensions import db


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False, index=True)
    roll_number = db.Column(db.String(40), nullable=False, unique=True, index=True)
    email = db.Column(db.String(254), nullable=False, unique=True, index=True)
    phone_number = db.Column(db.String(25), nullable=False)
    department = db.Column(db.String(100), nullable=False, index=True)
    course = db.Column(db.String(120), nullable=False)
    year_of_study = db.Column(db.Integer, nullable=False)
    date_of_admission = db.Column(db.Date, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "roll_number": self.roll_number,
            "email": self.email,
            "phone_number": self.phone_number,
            "department": self.department,
            "course": self.course,
            "year_of_study": self.year_of_study,
            "date_of_admission": str(self.date_of_admission.year),
        }
