from django.db import models
from django.utils.text import slugify
from django.conf import settings
from core.models import TimeStampedModel

class Genre(TimeStampedModel):
    """
    Movie Genre taxonomy classification (e.g., Action, Sci-Fi, Drama).
    Enables multi-facet filtering in movie discovery listings.
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Genre Name",
        help_text="Name of the movie genre category."
    )
    slug = models.SlugField(
        max_length=60,
        unique=True,
        blank=True,
        help_text="URL-friendly slug generated from genre name."
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Genre'
        verbose_name_plural = 'Genres'

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Language(TimeStampedModel):
    """
    Spoken language classification for movie audio/subtitles (e.g., English, Hindi, Telugu).
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Language Name",
        help_text="Name of the language."
    )
    code = models.CharField(
        max_length=10,
        unique=True,
        help_text="ISO language code (e.g. en, hi, te, ta)."
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Language'
        verbose_name_plural = 'Languages'

    def __str__(self):
        return self.name


class Cast(TimeStampedModel):
    """
    Actor, Actress, or Crew member metadata integrated with TMDb credit metadata.
    """
    tmdb_id = models.IntegerField(
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Unique TMDb person identifier."
    )
    name = models.CharField(
        max_length=150,
        db_index=True,
        verbose_name="Cast Member Name",
        help_text="Full legal or stage name of actor/crew."
    )
    character_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Character Name",
        help_text="Role played in movie (e.g. Tony Stark)."
    )
    profile_image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="TMDb profile image thumbnail URL."
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Cast Member'
        verbose_name_plural = 'Cast Members'

    def __str__(self):
        return self.name


class Movie(TimeStampedModel):
    """
    Core Movie catalog entity integrated with TMDb API.
    Stores metadata, media pointers, taxonomic tags, and classification ratings.
    """
    CATEGORY_CHOICES = (
        ('now_playing', 'Now Playing'),
        ('popular', 'Popular'),
        ('top_rated', 'Top Rated'),
        ('upcoming', 'Upcoming'),
    )

    CERTIFICATE_CHOICES = (
        ('U', 'U - Unrestricted Public Exhibition'),
        ('UA', 'UA - Parental Guidance for Children Under 12'),
        ('A', 'A - Restricted to Adults'),
        ('S', 'S - Restricted to Special Class'),
    )

    tmdb_id = models.IntegerField(
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Unique TMDb movie ID for automated synchronization."
    )
    title = models.CharField(
        max_length=200,
        db_index=True,
        verbose_name="Movie Title",
        help_text="Official release title of the movie."
    )
    slug = models.SlugField(
        max_length=220,
        unique=True,
        blank=True,
        help_text="SEO-friendly URL identifier."
    )
    tagline = models.CharField(
        max_length=300,
        blank=True,
        help_text="Promotional tagline phrase."
    )
    description = models.TextField(
        verbose_name="Synopsis",
        help_text="Full narrative plot overview."
    )

    # Media & Visual Assets
    poster = models.ImageField(
        upload_to='posters/',
        blank=True,
        null=True,
        help_text="Locally uploaded high-resolution poster image."
    )
    poster_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Official remote TMDb poster CDN URL."
    )
    backdrop_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Official remote TMDb banner/backdrop CDN URL."
    )
    trailer_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="YouTube embed link for official trailer video."
    )

    # Production Credits & Classification
    director = models.CharField(
        max_length=200,
        blank=True,
        help_text="Name of movie director(s)."
    )
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default='popular',
        db_index=True,
        help_text="Listing category tier on homepage."
    )
    certificate = models.CharField(
        max_length=5,
        choices=CERTIFICATE_CHOICES,
        default='UA',
        help_text="Censor board age rating certificate."
    )

    # Relationships & Taxonomies
    genres = models.ManyToManyField(
        Genre,
        related_name='movies',
        help_text="Taxonomic genres associated with this movie."
    )
    language = models.ForeignKey(
        Language,
        on_delete=models.PROTECT,
        related_name='movies',
        help_text="Primary audio language of the movie."
    )
    cast_members = models.ManyToManyField(
        Cast,
        blank=True,
        related_name='movies',
        help_text="Actors and crew featured in the movie."
    )

    # Metrics & Runtime
    duration = models.PositiveIntegerField(
        help_text="Total runtime duration in minutes (e.g. 148)."
    )
    release_date = models.DateField(
        db_index=True,
        help_text="Official theatrical release date."
    )
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=8.0,
        db_index=True,
        help_text="Aggregate rating score out of 10.0."
    )
    popularity = models.IntegerField(
        default=100,
        db_index=True,
        help_text="Calculated popularity score used for sorting catalog items."
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Boolean flag controlling visibility in public listings."
    )

    class Meta:
        ordering = ['-popularity', '-release_date']
        verbose_name = 'Movie'
        verbose_name_plural = 'Movies'
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['category']),
            models.Index(fields=['-popularity']),
            models.Index(fields=['-rating']),
            models.Index(fields=['-release_date']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Movie.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        year_str = self.release_date.year if self.release_date else ''
        return f"{self.title} ({year_str})"

    @property
    def get_poster_url(self):
        """Returns local uploaded poster URL, normalized TMDb poster URL, or clean fallback."""
        from movies.utils.images import normalize_image_url, FALLBACK_POSTER
        if self.poster:
            try:
                if hasattr(self.poster, 'url') and self.poster.name:
                    return self.poster.url
            except Exception:
                pass
        if self.poster_url:
            return normalize_image_url(self.poster_url, size='w500', is_backdrop=False)
        return FALLBACK_POSTER

    @property
    def get_backdrop_url(self):
        """Returns normalized official TMDb backdrop URL, or poster URL / clean fallback."""
        from movies.utils.images import normalize_image_url
        if self.backdrop_url:
            return normalize_image_url(self.backdrop_url, size='w1280', is_backdrop=True)
        return self.get_poster_url

    @property
    def formatted_duration(self):
        hours = self.duration // 60
        mins = self.duration % 60
        return f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

    @property
    def get_clean_trailer_url(self):
        """Returns high-compatibility YouTube embed URL."""
        from movies.utils.tmdb import get_safe_youtube_embed_url
        if self.trailer_url:
            clean_url = get_safe_youtube_embed_url(self.trailer_url)
            return clean_url if clean_url else self.trailer_url
        return ''

    @property
    def trailer_youtube_key(self):
        """Extracts the 11-character YouTube video ID from trailer_url."""
        from movies.utils.tmdb import extract_youtube_id
        return extract_youtube_id(self.trailer_url) if self.trailer_url else ''

    @property
    def has_trailer(self):
        """Returns True if a valid trailer key or URL is present."""
        return bool(self.trailer_youtube_key or self.trailer_url)

    @property
    def get_youtube_watch_url(self):
        """Returns direct YouTube watch URL or official trailer search link fallback."""
        from movies.utils.tmdb import get_youtube_watch_url
        return get_youtube_watch_url(self.trailer_url, title=self.title)




    @property
    def has_active_shows(self):
        """Returns True if the movie has any active future shows open for booking."""
        if hasattr(self, '_has_active_shows'):
            return self._has_active_shows
        from django.utils import timezone
        return self.shows.filter(start_time__gte=timezone.now(), status='OPEN').exists()

    @has_active_shows.setter
    def has_active_shows(self, value):
        self._has_active_shows = value


class Poster(TimeStampedModel):
    """
    Gallery Posters entity supporting multi-image showcases for movies.
    """
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='posters',
        help_text="Associated parent movie."
    )
    image = models.ImageField(
        upload_to='movie_gallery/',
        blank=True,
        null=True,
        help_text="Uploaded poster image file."
    )
    image_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Remote poster image CDN URL."
    )
    is_primary = models.BooleanField(
        default=False,
        help_text="Designates if this poster is the primary showcase banner."
    )

    class Meta:
        ordering = ['-is_primary', '-created_at']
        verbose_name = 'Movie Poster'
        verbose_name_plural = 'Movie Posters'

    @property
    def get_image_url(self):
        """Returns normalized image URL for gallery poster."""
        from movies.utils.images import normalize_image_url, FALLBACK_POSTER
        if self.image:
            try:
                if hasattr(self.image, 'url') and self.image.name:
                    return self.image.url
            except Exception:
                pass
        if self.image_url:
            return normalize_image_url(self.image_url, size='w500', is_backdrop=False)
        return FALLBACK_POSTER

    def __str__(self):
        return f"Poster for {self.movie.title} ({'Primary' if self.is_primary else 'Gallery'})"


class RecentlyViewed(models.Model):
    """
    Stores recently viewed movies per authenticated user or anonymous session.
    Used for recommendation candidate generation and history carousels.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recently_viewed',
        null=True,
        blank=True,
        help_text="Authenticated user record."
    )
    session_key = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        db_index=True,
        help_text="Anonymous visitor session key."
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name='viewed_records',
        help_text="Target movie viewed."
    )
    viewed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-viewed_at']
        verbose_name = 'Recently Viewed'
        verbose_name_plural = 'Recently Viewed Movies'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'movie'],
                name='unique_user_recently_viewed',
                condition=models.Q(user__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['session_key', 'movie'],
                name='unique_session_recently_viewed',
                condition=models.Q(session_key__isnull=False)
            ),
        ]

    def __str__(self):
        user_identifier = self.user.email if self.user else f"Session: {self.session_key}"
        return f"{user_identifier} viewed {self.movie.title}"
