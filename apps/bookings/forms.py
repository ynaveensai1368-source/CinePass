from django import forms
from .models import Booking

class BookingForm(forms.ModelForm):
    seats_booked = forms.IntegerField(
        min_value=1,
        max_value=10,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10})
    )

    class Meta:
        model = Booking
        fields = ('seats_booked',)
