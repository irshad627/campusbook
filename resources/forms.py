from django import forms

from .models import Resource


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = ("name", "resource_type", "location", "capacity", "features", "student_bookable", "shared")