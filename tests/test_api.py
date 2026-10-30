from datetime import date
import unittest

from app import create_app
from app import _database_url
from app.extensions import db
from app.models import Student


def student_payload(**overrides):
    payload = {
        "full_name": "Avery Morgan",
        "roll_number": "CS-2025-014",
        "email": "avery@example.edu",
        "phone_number": "+1 (555) 123-4567",
        "department": "Computer Science",
        "course": "BSc Computer Science",
        "year_of_study": 2,
        "date_of_admission": str(date.today().year - 1),
    }
    payload.update(overrides)
    return payload


class StudentApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
            }
        )
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def create_student(self, **overrides):
        return self.client.post("/api/students", json=student_payload(**overrides))

    def test_postgresql_urls_use_psycopg_with_verified_ssl(self):
        configured_url = (
            "postgresql://user:secret@example.neon.tech/app"
            "?application_name=student-management&sslmode=require"
        )
        database_url = _database_url(configured_url)
        self.assertTrue(database_url.startswith("postgresql+psycopg://"))
        self.assertIn("sslmode=verify-full", database_url)
        self.assertIn("channel_binding=require", database_url)
        self.assertIn("application_name=student-management", database_url)

    def test_sqlite_database_url_remains_unchanged(self):
        self.assertEqual(_database_url("sqlite:///students.db"), "sqlite:///students.db")

    def test_dashboard_template_contains_separate_route_sections(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('data-page-section="overview"', html)
        self.assertIn('data-page-section="students"', html)
        self.assertIn('id="overview-student-rows"', html)
        self.assertIn('id="student-rows"', html)
        self.assertIn('id="student-search"', html)
        self.assertIn('id="department-filter"', html)

    def test_create_and_get_student(self):
        created = self.create_student()
        self.assertEqual(created.status_code, 201)
        student = created.get_json()["data"]
        self.assertEqual(student["full_name"], "Avery Morgan")
        self.assertEqual(student["date_of_admission"], str(date.today().year - 1))

        fetched = self.client.get(f"/api/students/{student['id']}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.get_json()["data"]["roll_number"], "CS-2025-014")

    def test_validation_and_duplicate_conflict(self):
        invalid = self.create_student(email="not-an-email", year_of_study=9)
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("email", invalid.get_json()["details"])
        self.assertIn("year_of_study", invalid.get_json()["details"])

        self.assertEqual(self.create_student().status_code, 201)
        duplicate = self.create_student(
            roll_number="cs-2025-014", email="other@example.edu"
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("roll_number", duplicate.get_json()["details"])

    def test_only_four_years_of_study_are_accepted(self):
        accepted = self.create_student(year_of_study=4)
        self.assertEqual(accepted.status_code, 201)
        rejected = self.create_student(
            full_name="Taylor Reed",
            roll_number="CS-2025-015",
            email="taylor@example.edu",
            year_of_study=5,
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertIn("year_of_study", rejected.get_json()["details"])

    def test_admission_year_accepts_only_valid_four_digit_years(self):
        current_year = date.today().year
        valid = self.create_student(date_of_admission=str(current_year))
        self.assertEqual(valid.status_code, 201)
        self.assertEqual(
            valid.get_json()["data"]["date_of_admission"], str(current_year)
        )

        invalid_years = (
            "123",
            "02026",
            "20a6",
            "20-6",
            "2026-01-01",
            "1899",
            str(current_year + 1),
        )
        for index, admission_year in enumerate(invalid_years):
            with self.subTest(admission_year=admission_year):
                response = self.create_student(
                    full_name=f"Invalid Year Student {index}",
                    roll_number=f"INVALID-{index}",
                    email=f"invalid{index}@example.edu",
                    date_of_admission=admission_year,
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("date_of_admission", response.get_json()["details"])

    def test_update_rejects_invalid_year_and_preserves_existing_record(self):
        student = self.create_student().get_json()["data"]
        invalid_study_year = self.client.put(
            f"/api/students/{student['id']}",
            json=student_payload(year_of_study=5),
        )
        self.assertEqual(invalid_study_year.status_code, 400)
        self.assertIn("year_of_study", invalid_study_year.get_json()["details"])

        response = self.client.put(
            f"/api/students/{student['id']}",
            json=student_payload(date_of_admission="20265"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("date_of_admission", response.get_json()["details"])
        unchanged = self.client.get(f"/api/students/{student['id']}").get_json()[
            "data"
        ]
        self.assertEqual(unchanged["date_of_admission"], str(date.today().year - 1))

    def test_legacy_years_remain_visible_but_charts_are_limited_to_four(self):
        legacy_student = Student(
            full_name="Legacy Student",
            roll_number="LEGACY-008",
            email="legacy@example.edu",
            phone_number="+1 555 123 4567",
            department="Legacy Department",
            course="Legacy Course",
            year_of_study=8,
            date_of_admission=date(2020, 9, 1),
        )
        db.session.add(legacy_student)
        db.session.commit()

        listed = self.client.get("/api/students").get_json()["data"]
        self.assertEqual(listed[0]["year_of_study"], 8)
        stats = self.client.get("/api/dashboard/stats").get_json()["data"]
        self.assertEqual([item["year"] for item in stats["by_year"]], [1, 2, 3, 4])
        self.assertEqual(
            self.client.get(f"/api/students/{legacy_student.id}")
            .get_json()["data"]["date_of_admission"],
            "2020",
        )

    def test_update_accepts_valid_fourth_year_and_admission_year(self):
        student = self.create_student().get_json()["data"]
        updated = self.client.put(
            f"/api/students/{student['id']}",
            json=student_payload(year_of_study=4, date_of_admission="2024"),
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["data"]["year_of_study"], 4)
        self.assertEqual(updated.get_json()["data"]["date_of_admission"], "2024")

    def test_search_and_department_filter(self):
        self.create_student()
        self.create_student(
            full_name="Jordan Lee",
            roll_number="BUS-2025-003",
            email="jordan@example.edu",
            department="Business",
            course="BBA",
        )

        result = self.client.get("/api/students?search=cs-2025")
        self.assertEqual(result.get_json()["count"], 1)
        filtered = self.client.get("/api/students?department=business")
        self.assertEqual(filtered.get_json()["data"][0]["full_name"], "Jordan Lee")

    def test_update_delete_and_dashboard_stats(self):
        student_id = self.create_student().get_json()["data"]["id"]
        updated = self.client.put(
            f"/api/students/{student_id}",
            json=student_payload(full_name="Avery Chen"),
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["data"]["full_name"], "Avery Chen")

        stats = self.client.get("/api/dashboard/stats").get_json()["data"]
        self.assertEqual(stats["total_students"], 1)
        self.assertEqual(stats["department_count"], 1)
        self.assertEqual(
            stats["by_year"],
            [
                {"year": 1, "count": 0},
                {"year": 2, "count": 1},
                {"year": 3, "count": 0},
                {"year": 4, "count": 0},
            ],
        )

        deleted = self.client.delete(f"/api/students/{student_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(
            self.client.get("/api/students").get_json()["count"],
            0,
        )

    def test_not_found_responses(self):
        self.assertEqual(self.client.get("/api/students/999").status_code, 404)
        self.assertEqual(self.client.delete("/api/students/999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
