# CampusBook

Campus facility and equipment booking system (CSE3101, Group 1).

## Setup

1. Install Python 3 and PostgreSQL.
2. Create a database named `campusbook`.
3. Copy `.env.example` to `.env` and enter your PostgreSQL password.
4. Create a virtual environment and install packages:
   - `py -m venv venv`
   - `venv\Scripts\Activate.ps1`
   - `pip install -r requirements.txt`
5. Create the tables: `py manage.py migrate`
6. Create an admin user: `py manage.py createsuperuser`
7. Start the server: `py manage.py runserver`
8. Open http://127.0.0.1:8000/

## Roles

Users register as Students. An administrator promotes users to Lecturer,
Facilities Staff or Administrator in the Django admin (`/admin/`).