"""
BookMyShow-Inspired Location & Language Aware Recommendation Engine for CinePass.
Implements multi-tiered recommendation hierarchy:
  1. Active showtime availability in user's selected location/city.
  2. Regional language prominence for that city.
  3. User genre affinity from booking history & viewing activity.
  4. Popularity, TMDb rating, and release date weighting.
  5. Fallbacks to popular city releases while preventing N+1 queries.
"""
from django.utils import timezone
from django.db.models import Q, Case, When, Value, IntegerField, Exists, OuterRef
from movies.models import Movie, RecentlyViewed
from bookings.models import Booking
from shows.models import Show
from theaters.models import City

# Genre affinity expansion
GENRE_AFFINITY_MAP = {
    'Action': ['Action', 'Adventure', 'Thriller', 'Sci-Fi'],
    'Drama': ['Drama', 'Romance', 'Biography', 'Crime'],
    'Comedy': ['Comedy', 'Animation', 'Family'],
    'Sci-Fi': ['Sci-Fi', 'Action', 'Adventure', 'Mystery'],
    'Horror': ['Horror', 'Thriller', 'Mystery'],
    'Thriller': ['Thriller', 'Crime', 'Action', 'Mystery'],
    'Animation': ['Animation', 'Family', 'Adventure', 'Comedy'],
    'Adventure': ['Adventure', 'Action', 'Fantasy', 'Sci-Fi'],
}

# Regional language prominence ranking by City slug/name
CITY_REGIONAL_LANGUAGES = {
    'hyderabad': ['te', 'en', 'hi', 'ta', 'ml', 'kn'],
    'chennai': ['ta', 'en', 'te', 'ml', 'hi', 'kn'],
    'mumbai': ['hi', 'mr', 'en', 'gu', 'ta', 'te'],
    'bengaluru': ['kn', 'en', 'te', 'ta', 'hi', 'ml'],
    'delhi-ncr': ['hi', 'en', 'pa', 'ur', 'ta', 'te'],
    'pune': ['mr', 'hi', 'en', 'gu', 'ta'],
    'kochi': ['ml', 'en', 'ta', 'hi', 'te'],
    'kolkata': ['bn', 'hi', 'en'],
    'ahmedabad': ['gu', 'hi', 'en'],
}


def get_city_language_priority(city):
    """Returns the ordered list of primary language codes for a given city."""
    if not city:
        return ['en', 'hi', 'te', 'ta']
    c_key = city.name.lower().replace(' ', '-')
    if c_key in CITY_REGIONAL_LANGUAGES:
        return CITY_REGIONAL_LANGUAGES[c_key]
    for k, langs in CITY_REGIONAL_LANGUAGES.items():
        if k in c_key or c_key in k:
            return langs
    return ['en', 'hi', 'te', 'ta', 'ml', 'kn']


def get_personalized_recommendations(user=None, session_key=None, city=None, limit=6):
    """
    Computes real location-based and language-aware movie recommendations.
    Hierarchy:
      1. Movies currently playing or upcoming in `city`.
      2. Regional language affinity for `city`.
      3. Genre affinity from user booking history & recently viewed.
      4. Exclude already booked movies.
      5. Rank by showtime availability + language match + popularity/rating.
    """
    now = timezone.now()
    booked_movie_ids = set()
    preferred_genre_names = set()

    # 1. Analyze User Booking History
    if user and user.is_authenticated:
        user_bookings = Booking.objects.filter(
            user=user,
            status='CONFIRMED'
        ).select_related('show__movie').prefetch_related('show__movie__genres')

        for booking in user_bookings:
            if booking.show and booking.show.movie:
                m = booking.show.movie
                booked_movie_ids.add(m.id)
                for genre in m.genres.all():
                    preferred_genre_names.add(genre.name)
                    for mapped in GENRE_AFFINITY_MAP.get(genre.name, []):
                        preferred_genre_names.add(mapped)

    # 2. Analyze Recently Viewed Movies
    recent_qs = RecentlyViewed.objects.none()
    if user and user.is_authenticated:
        recent_qs = RecentlyViewed.objects.filter(user=user)
    elif session_key:
        recent_qs = RecentlyViewed.objects.filter(session_key=session_key)

    recent_viewed = recent_qs.select_related('movie').prefetch_related('movie__genres')[:5]
    for rv in recent_viewed:
        if rv.movie:
            for genre in rv.movie.genres.all():
                preferred_genre_names.add(genre.name)
                for mapped in GENRE_AFFINITY_MAP.get(genre.name, []):
                    preferred_genre_names.add(mapped)

    # 3. Base Queryset
    city_shows_subquery = None
    if city:
        city_shows_subquery = Show.objects.filter(
            movie=OuterRef('pk'),
            screen__theater__city=city,
            start_time__gte=now,
            status='OPEN'
        )
    else:
        city_shows_subquery = Show.objects.filter(
            movie=OuterRef('pk'),
            start_time__gte=now,
            status='OPEN'
        )

    base_qs = Movie.objects.filter(is_active=True)\
        .annotate(
            has_active_shows=Exists(city_shows_subquery),
            has_city_shows=Exists(city_shows_subquery)
        )\
        .select_related('language').prefetch_related('genres')

    if booked_movie_ids:
        base_qs = base_qs.exclude(id__in=booked_movie_ids)

    # 4. Regional Language Priority Cases
    priority_langs = get_city_language_priority(city)
    lang_whens = []
    for idx, lcode in enumerate(priority_langs):
        # Weight higher for primary regional languages
        weight = 100 - (idx * 15)
        lang_whens.append(When(language__code=lcode, then=Value(weight)))
    
    lang_priority_expr = Case(
        *lang_whens,
        default=Value(10),
        output_field=IntegerField()
    )

    # Genre affinity score
    genre_priority_expr = Value(0)
    if preferred_genre_names:
        genre_priority_expr = Case(
            When(genres__name__in=preferred_genre_names, then=Value(50)),
            default=Value(0),
            output_field=IntegerField()
        )

    scored_qs = base_qs.annotate(
        lang_score=lang_priority_expr,
        genre_score=genre_priority_expr,
        city_score=Case(
            When(has_city_shows=True, then=Value(200)),
            default=Value(0),
            output_field=IntegerField()
        )
    )

    # Order by: Active in city -> Regional language fit -> Genre affinity -> Popularity -> Rating -> Release Date
    ordered_recs = scored_qs.order_by(
        '-city_score',
        '-lang_score',
        '-genre_score',
        '-popularity',
        '-rating',
        '-release_date'
    ).distinct()

    recs = list(ordered_recs[:limit])

    # If count is below limit, fill with active popular movies
    if len(recs) < limit:
        existing_ids = {m.id for m in recs} | booked_movie_ids
        fillers = base_qs.exclude(id__in=existing_ids).order_by('-popularity', '-rating')[:(limit - len(recs))]
        recs.extend(list(fillers))

    return recs[:limit]
