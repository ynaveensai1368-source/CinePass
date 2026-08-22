"""
Intelligent Recommendation Engine for Movie Discovery System.
Implements genre affinity matching, recently viewed weighting, and popularity fallbacks while preventing N+1 queries.
"""
from django.db.models import Q, Count
from movies.models import Movie, RecentlyViewed
from bookings.models import Booking

GENRE_AFFINITY_MAP = {
    'Action': ['Action', 'Adventure', 'Thriller', 'Sci-Fi'],
    'Drama': ['Drama', 'Romance', 'Biography'],
    'Comedy': ['Comedy', 'Animation', 'Family'],
    'Sci-Fi': ['Sci-Fi', 'Action', 'Adventure', 'Mystery'],
    'Horror': ['Horror', 'Thriller', 'Mystery'],
    'Thriller': ['Thriller', 'Crime', 'Action', 'Mystery'],
}

def get_personalized_recommendations(user=None, session_key=None, limit=6):
    """
    Returns recommended movies for a user or session.
    1. Extracts booked genres and recently viewed genres.
    2. Excludes already booked movies.
    3. Maps genre affinities (e.g. Action -> Action, Adventure, Thriller).
    4. Fallbacks to top popular movies if insufficient user history.
    """
    booked_movie_ids = set()
    preferred_genre_names = set()

    # Step 1: User booking history analysis
    if user and user.is_authenticated:
        user_bookings = Booking.objects.filter(
            user=user,
            status='CONFIRMED'
        ).select_related('show__movie').prefetch_related('show__movie__genres')

        for booking in user_bookings:
            movie = booking.show.movie
            booked_movie_ids.add(movie.id)
            for genre in movie.genres.all():
                preferred_genre_names.add(genre.name)
                # Add mapped genre affinities
                for mapped_genre in GENRE_AFFINITY_MAP.get(genre.name, []):
                    preferred_genre_names.add(mapped_genre)

    # Step 2: Incorporate recently viewed movies
    recent_qs = RecentlyViewed.objects.none()
    if user and user.is_authenticated:
        recent_qs = RecentlyViewed.objects.filter(user=user)
    elif session_key:
        recent_qs = RecentlyViewed.objects.filter(session_key=session_key)

    recent_viewed = recent_qs.select_related('movie').prefetch_related('movie__genres')[:5]
    for rv in recent_viewed:
        for genre in rv.movie.genres.all():
            preferred_genre_names.add(genre.name)
            for mapped_genre in GENRE_AFFINITY_MAP.get(genre.name, []):
                preferred_genre_names.add(mapped_genre)

    # Step 3: Fetch recommendation queryset
    base_qs = Movie.objects.filter(is_active=True).select_related('language').prefetch_related('genres').distinct()

    if booked_movie_ids:
        base_qs = base_qs.exclude(id__in=booked_movie_ids)

    if preferred_genre_names:
        rec_qs = base_qs.filter(genres__name__in=preferred_genre_names).order_by('-popularity', '-rating')[:limit]
        recs = list(rec_qs)
        
        # If recommendation count is less than required limit, fill with top popular movies
        if len(recs) < limit:
            existing_ids = {m.id for m in recs} | booked_movie_ids
            fallback = base_qs.exclude(id__in=existing_ids).order_by('-popularity', '-rating')[:(limit - len(recs))]
            recs.extend(list(fallback))
        return recs[:limit]

    # Step 4: Fallback to top trending popular movies for new/guest users
    fallback_recs = list(base_qs.order_by('-popularity', '-rating')[:limit])
    return fallback_recs
