from django import forms
from .models import Movie, Genre, Language

class MovieForm(forms.ModelForm):
    genres = forms.ModelMultipleChoiceField(
        queryset=Genre.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=True
    )

    class Meta:
        model = Movie
        fields = ('title', 'description', 'poster', 'trailer_url', 'genres', 'language', 'duration', 'release_date', 'rating', 'popularity', 'is_active')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Movie Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Synopsis'}),
            'poster': forms.FileInput(attrs={'class': 'form-control'}),
            'trailer_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://youtube.com/embed/...'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Duration in minutes'}),
            'release_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0', 'max': '10'}),
            'popularity': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_trailer_url(self):
        trailer_url = self.cleaned_data.get('trailer_url')
        if trailer_url:
            from movies.tmdb_service import get_safe_youtube_embed_url
            clean_url = get_safe_youtube_embed_url(trailer_url)
            return clean_url if clean_url else trailer_url
        return trailer_url
