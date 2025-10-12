"""
Django management command to import Departments, Courses, Guides and PhD Students
from CSV files. Each CSV file is optional – only the provided ones are processed.

Typical usage::

    python manage.py import_entities \
        --departments path/to/departments.csv \
        --courses path/to/courses.csv \
        --guides path/to/guides.csv \
        --students path/to/students.csv

The command is idempotent; existing records (matched by unique key) are updated,
otherwise new ones are created.
"""

import csv
from pathlib import Path
from typing import Dict, Tuple

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from users.models import Department, Course, Guide, PhDStudent, User

CSV_OPEN_OPTS = {
    "newline": "",
    "encoding": "utf-8-sig",  # handles BOM if present
}


class Command(BaseCommand):
    help = "Import Departments, Courses, Guides and PhD Students from CSV files."

    def add_arguments(self, parser):
        parser.add_argument("--departments", help="Path to departments CSV", default=None)
        parser.add_argument("--courses", help="Path to courses CSV", default=None)
        parser.add_argument("--guides", help="Path to guides CSV", default=None)
        parser.add_argument("--students", help="Path to students CSV", default=None)

    # ---------------------------------------------------------------------
    # Helper import functions
    # ---------------------------------------------------------------------
    def _open_reader(self, file_path: str):
        """Return csv.DictReader for given path or raise error."""
        if not Path(file_path).exists():
            raise CommandError(f"File not found: {file_path}")
        f = open(file_path, mode="r", **CSV_OPEN_OPTS)
        return csv.DictReader(f), f

    def _required(self, row: Dict[str, str], *fields: str):
        """Ensure required columns are present and non-blank."""
        for field in fields:
            if not row.get(field):
                raise CommandError(f"Missing required field '{field}' in row: {row}")

    # ------------------------------------------------------------------
    # Importers
    # ------------------------------------------------------------------
    def import_departments(self, csv_path: str) -> Tuple[int, int]:
        created = updated = 0
        reader, fh = self._open_reader(csv_path)
        with fh, transaction.atomic():
            for row in reader:
                self._required(row, "code", "name")
                defaults = {
                    "name": row["name"],
                    "faculty": row.get("faculty"),
                    "head_of_department": row.get("head_of_department", ""),
                    "contact_email": row.get("contact_email", ""),
                    "phone": row.get("phone", ""),
                }
                obj, created_flag = Department.objects.update_or_create(
                    code=row["code"], defaults=defaults
                )
                created += int(created_flag)
                updated += int(not created_flag)
        return created, updated

    def import_courses(self, csv_path: str) -> Tuple[int, int]:
        created = updated = 0
        reader, fh = self._open_reader(csv_path)
        with fh, transaction.atomic():
            for row in reader:
                self._required(row, "code", "name", "department_code")
                try:
                    dept = Department.objects.get(code=row["department_code"])
                except Department.DoesNotExist:
                    raise CommandError(
                        f"Department code {row['department_code']} not found for course {row['code']}"
                    )
                defaults = {
                    "name": row["name"],
                    "department": dept,
                    "credits": row.get("credits") or 0,
                    "min_project_semester": row.get("min_project_semester") or 1,
                    "fee_per_semester": row.get("fee_per_semester") or 0,
                }
                obj, created_flag = Course.objects.update_or_create(
                    code=row["code"], defaults=defaults
                )
                created += int(created_flag)
                updated += int(not created_flag)
        return created, updated

    def import_guides(self, csv_path: str) -> Tuple[int, int]:
        created = updated = 0
        reader, fh = self._open_reader(csv_path)
        with fh, transaction.atomic():
            for row in reader:
                self._required(row, "email", "name", "department_code")
                dept = Department.objects.filter(code=row["department_code"]).first()
                if not dept:
                    raise CommandError(
                        f"Department code {row['department_code']} not found for guide {row['email']}"
                    )
                defaults = {
                    "name": row["name"],
                    "department": dept,
                    "is_hod": row.get("is_hod", "false").lower() == "true",
                    "designation": row.get("designation", ""),
                    "specialization": row.get("specialization", ""),
                    "phone": row.get("phone", ""),
                    "is_active": row.get("is_active", "true").lower() != "false",
                    "max_students": int(row.get("max_students") or 5),
                }
                obj, created_flag = Guide.objects.update_or_create(
                    email=row["email"], defaults=defaults
                )
                # Also ensure corresponding User exists for authentication
                if created_flag:
                    User.objects.get_or_create(
                        email=obj.email,
                        defaults={
                            "role": User.Role.GUIDE,
                            "is_active": obj.is_active,
                            "is_staff": False,
                            "date_joined": timezone.now(),
                            "password": User.objects.make_random_password(),
                        },
                    )
                created += int(created_flag)
                updated += int(not created_flag)
        return created, updated

    def import_students(self, csv_path: str) -> Tuple[int, int]:
        created = updated = 0
        reader, fh = self._open_reader(csv_path)
        with fh, transaction.atomic():
            for row in reader:
                self._required(row, "student_id", "name", "email", "course_code")
                course = Course.objects.filter(code=row["course_code"]).first()
                if not course:
                    raise CommandError(
                        f"Course code {row['course_code']} not found for student {row['student_id']}"
                    )
                guide = None
                if row.get("guide_email"):
                    guide = Guide.objects.filter(email=row["guide_email"]).first()
                    if not guide:
                        self.stderr.write(
                            self.style.WARNING(
                                f"Guide {row['guide_email']} not found; continuing without guide for {row['student_id']}"
                            )
                        )
                defaults = {
                    "name": row["name"],
                    "email": row["email"],
                    "course": course,
                    "guide": guide,
                    "enrollment_date": row.get("enrollment_date") or timezone.now().date(),
                    "current_semester": int(row.get("current_semester") or 1),
                    "status": row.get("status") or "ENROLLED",
                    "phone": row.get("phone", ""),
                    "address": row.get("address", ""),
                    "is_active": row.get("is_active", "true").lower() != "false",
                }
                obj, created_flag = PhDStudent.objects.update_or_create(
                    student_id=row["student_id"], defaults=defaults
                )
                # create associated User
                if created_flag:
                    User.objects.get_or_create(
                        email=obj.email,
                        defaults={
                            "role": User.Role.STUDENT,
                            "is_active": obj.is_active,
                            "date_joined": timezone.now(),
                            "password": User.objects.make_random_password(),
                        },
                    )
                created += int(created_flag)
                updated += int(not created_flag)
        return created, updated

    # ------------------------------------------------------------------
    # Command entry
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        summary = {}
        if options["departments"]:
            summary["departments"] = self.import_departments(options["departments"])
            self.stdout.write(self.style.SUCCESS(
                f"Departments imported – created:{summary['departments'][0]} updated:{summary['departments'][1]}"
            ))
        if options["courses"]:
            summary["courses"] = self.import_courses(options["courses"])
            self.stdout.write(self.style.SUCCESS(
                f"Courses imported – created:{summary['courses'][0]} updated:{summary['courses'][1]}"
            ))
        if options["guides"]:
            summary["guides"] = self.import_guides(options["guides"])
            self.stdout.write(self.style.SUCCESS(
                f"Guides imported – created:{summary['guides'][0]} updated:{summary['guides'][1]}"
            ))
        if options["students"]:
            summary["students"] = self.import_students(options["students"])
            self.stdout.write(self.style.SUCCESS(
                f"Students imported – created:{summary['students'][0]} updated:{summary['students'][1]}"
            ))

        if not summary:
            self.stdout.write(self.style.WARNING("No CSV files provided. Nothing imported."))
