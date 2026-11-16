from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    #Data structure that stores choices 
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        LECTURER = "lecturer", "Lecturer"
        STAFF = "staff", "Facilities Staff"
        ADMIN = "admin", "Administrator"

    #Adds the actual column to the table
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
    )