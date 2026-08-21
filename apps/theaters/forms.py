from django import forms
from .models import City, Theater, Screen
from shows.models import Show

class CityForm(forms.ModelForm):
    class Meta:
        model = City
        fields = ('name', 'state')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'City Name'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State / Province'}),
        }


class TheaterForm(forms.ModelForm):
    class Meta:
        model = Theater
        fields = ('name', 'city', 'address', 'latitude', 'longitude')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Theater Name'}),
            'city': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Full Street Address'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001'}),
        }


class ScreenForm(forms.ModelForm):
    class Meta:
        model = Screen
        fields = ('theater', 'name', 'screen_type', 'total_seats')
        widgets = {
            'theater': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Screen Name'}),
            'screen_type': forms.Select(attrs={'class': 'form-select'}),
            'total_seats': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class ShowForm(forms.ModelForm):
    class Meta:
        model = Show
        fields = ('movie', 'screen', 'start_time', 'end_time', 'base_price', 'status', 'available_seats')
        widgets = {
            'movie': forms.Select(attrs={'class': 'form-select'}),
            'screen': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.50'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'available_seats': forms.NumberInput(attrs={'class': 'form-control'}),
        }
