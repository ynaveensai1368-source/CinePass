from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView

import datetime
import logging
from django.db.models import Q, Min, Max, Avg, Count, Exists, OuterRef
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone

from .models import Movie, Genre, Language, RecentlyViewed
from theaters.models import City, Theater
from shows.models import Show
from .forms import MovieForm
from .recommendations import get_personalized_recommendations

logger = logging.getLogger(__name__)


def ensure_movies_seeded():
    """Defensive helper ensuring database has movie catalog populated on any deployment environment."""
    try:
        if Movie.objects.filter(is_active=True).exclude(poster_url__isnull=True).exclude(poster_url='').count() < 5:
            from django.core.management import call_command
            logger.info("Empty or outdated movie catalog detected. Auto-seeding production movie catalog...")
            call_command('seed_data')
    except Exception as e:
        logger.warning(f"Auto-seeding check warning: {e}")


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff


class HomeView(TemplateView):
    template_name = 'movies/home.html'

    def get_context_data(self, **kwargs):
        ensure_movies_seeded()
        context = super().get_context_data(**kwargs)
        
        if not self.request.session.session_key:
            self.request.session.save()
        session_key = self.request.session.session_key

        today = timezone.now().date()
        ninety_days_ago = today - datetime.timedelta(days=90)

        # Subquery to check for active future open shows
        active_shows_subquery = Show.objects.filter(
            movie=OuterRef('pk'),
            start_time__gte=timezone.now(),
            status='OPEN'
        )

        # Base optimized queryset
        base_movies = Movie.objects.filter(is_active=True)\
            .annotate(has_active_shows=Exists(active_shows_subquery))\
            .select_related('language').prefetch_related('genres')

        # Hero Banner Movies (Top 5 by popularity with high-res TMDb backdrops, or top popular movies)
        hero_qs = base_movies.exclude(backdrop_url__isnull=True).exclude(backdrop_url='').order_by('-popularity')[:5]
        if not hero_qs.exists():
            hero_qs = base_movies.order_by('-popularity')[:5]
        context['hero_movies'] = hero_qs

        # Category Collections
        # 1. Now Playing in Theaters: Confirmed active shows OR recent release/now_playing category
        now_playing_qs = base_movies.filter(
            Q(has_active_shows=True) | Q(category='now_playing') | Q(release_date__gte=ninety_days_ago, release_date__lte=today)
        ).order_by('-release_date', '-popularity')[:6]
        context['now_playing'] = now_playing_qs

        context['popular_movies'] = base_movies.order_by('-popularity', '-rating')[:6]
        context['top_rated_movies'] = base_movies.order_by('-rating', '-popularity')[:6]
        
        upcoming_qs = base_movies.filter(
            Q(category='upcoming') | Q(release_date__gt=today)
        ).order_by('release_date', '-popularity')[:6]
        if not upcoming_qs.exists():
            upcoming_qs = base_movies.order_by('-release_date')[:6]
        context['upcoming_movies'] = upcoming_qs

        # Personalized Recommendations
        context['recommended_movies'] = get_personalized_recommendations(
            user=self.request.user if self.request.user.is_authenticated else None,
            session_key=session_key,
            limit=6
        )

        # Recently Viewed Movies
        rv_qs = RecentlyViewed.objects.none()
        if self.request.user.is_authenticated:
            rv_qs = RecentlyViewed.objects.filter(user=self.request.user)
        elif session_key:
            rv_qs = RecentlyViewed.objects.filter(session_key=session_key)

        context['recently_viewed'] = [
            rv.movie for rv in rv_qs.select_related('movie__language').prefetch_related('movie__genres')[:6]
        ]

        context['cities'] = City.objects.all()
        return context


class MovieDiscoveryView(ListView):
    model = Movie
    template_name = 'movies/movie_list.html'
    context_object_name = 'movies'
    paginate_by = 12

    def get_queryset(self):
        ensure_movies_seeded()
        active_shows_subquery = Show.objects.filter(
            movie=OuterRef('pk'),
            start_time__gte=timezone.now(),
            status='OPEN'
        )
        qs = Movie.objects.filter(is_active=True)\
            .annotate(has_active_shows=Exists(active_shows_subquery))\
            .select_related('language').prefetch_related('genres').annotate(
                min_price=Min('shows__base_price'),
                max_price=Max('shows__base_price')
            )

        # 1. Search Query
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(director__icontains=search_query)
            )

        # 2. Multi-Facet Filters
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category=category)

        genre_id = self.request.GET.get('genre')
        if genre_id:
            qs = qs.filter(genres__id=genre_id)

        language_id = self.request.GET.get('language')
        if language_id:
            qs = qs.filter(language__id=language_id)

        city_id = self.request.GET.get('city')
        if city_id:
            qs = qs.filter(shows__screen__theater__city__id=city_id)

        theater_id = self.request.GET.get('theater')
        if theater_id:
            qs = qs.filter(shows__screen__theater__id=theater_id)

        min_rating = self.request.GET.get('rating')
        if min_rating:
            try:
                qs = qs.filter(rating__gte=float(min_rating))
            except ValueError:
                pass

        release_year = self.request.GET.get('release_date')
        if release_year:
            if release_year == 'upcoming':
                qs = qs.filter(release_date__gt=timezone.now().date())
            elif release_year == 'recent':
                qs = qs.filter(release_date__lte=timezone.now().date())

        # Show Timing Filter (Morning, Afternoon, Evening, Night)
        show_time_slot = self.request.GET.get('show_time')
        if show_time_slot:
            if show_time_slot == 'morning':
                qs = qs.filter(shows__start_time__time__gte='06:00:00', shows__start_time__time__lt='12:00:00')
            elif show_time_slot == 'afternoon':
                qs = qs.filter(shows__start_time__time__gte='12:00:00', shows__start_time__time__lt='16:00:00')
            elif show_time_slot == 'evening':
                qs = qs.filter(shows__start_time__time__gte='16:00:00', shows__start_time__time__lt='20:00:00')
            elif show_time_slot == 'night':
                qs = qs.filter(Q(shows__start_time__time__gte='20:00:00') | Q(shows__start_time__time__lt='06:00:00'))

        # 3. Sorting
        sort_by = self.request.GET.get('sort', 'popularity')
        if sort_by == 'newest':
            qs = qs.order_by('-release_date', '-popularity')
        elif sort_by == 'rating':
            qs = qs.order_by('-rating', '-popularity')
        elif sort_by == 'price_low':
            qs = qs.order_by('min_price', '-popularity')
        elif sort_by == 'price_high':
            qs = qs.order_by('-max_price', '-popularity')
        else:
            qs = qs.order_by('-popularity', '-rating')

        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['genres'] = Genre.objects.all()
        context['languages'] = Language.objects.all()
        context['cities'] = City.objects.all()
        context['theaters'] = Theater.objects.select_related('city').all()
        
        context['current_search'] = self.request.GET.get('q', '')
        context['current_category'] = self.request.GET.get('category', '')
        context['current_genre'] = self.request.GET.get('genre', '')
        context['current_language'] = self.request.GET.get('language', '')
        context['current_city'] = self.request.GET.get('city', '')
        context['current_theater'] = self.request.GET.get('theater', '')
        context['current_rating'] = self.request.GET.get('rating', '')
        context['current_sort'] = self.request.GET.get('sort', 'popularity')
        context['current_release'] = self.request.GET.get('release_date', '')
        context['current_show_time'] = self.request.GET.get('show_time', '')

        get_copy = self.request.GET.copy()
        if 'page' in get_copy:
            del get_copy['page']
        context['querystring'] = get_copy.urlencode()

        context['movie_count'] = self.get_queryset().count()
        return context


class MovieDetailView(DetailView):
    model = Movie
    template_name = 'movies/movie_detail.html'
    context_object_name = 'movie'

    def get_queryset(self):
        return Movie.objects.select_related('language').prefetch_related('genres', 'cast_members', 'posters')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        movie = self.object

        # Resilient dynamic fetch of trailer & cast from TMDb if missing
        try:
            # 1. Resolve TMDb ID by title & release year if missing
            if not movie.tmdb_id:
                from movies.utils.tmdb import search_tmdb_movie_id
                year = movie.release_date.year if movie.release_date else None
                found_id = search_tmdb_movie_id(movie.title, release_year=year)
                if found_id:
                    movie.tmdb_id = found_id
                    movie.save(update_fields=['tmdb_id'])

            # 2. Dynamic multi-priority trailer discovery
            if movie.tmdb_id:
                if not movie.trailer_url:
                    from movies.utils.tmdb import get_movie_trailer_data
                    orig_lang = movie.language.code if movie.language else None
                    t_data = get_movie_trailer_data(movie.tmdb_id, original_language=orig_lang, title=movie.title)
                    if t_data and t_data.get('embed_url'):
                        movie.trailer_url = t_data['embed_url']
                        movie.save(update_fields=['trailer_url'])

                # 3. Auto-sync cast credits if missing
                if not movie.cast_members.exists():
                    from .tmdb_service import fetch_and_sync_movie_credits
                    fetch_and_sync_movie_credits(movie)
        except Exception as e:
            logger.warning(f"TMDb dynamic sync warning for {movie.title}: {e}")

        context['trailer_url'] = movie.trailer_url
        context['trailer_youtube_key'] = movie.trailer_youtube_key
        context['has_trailer'] = movie.has_trailer


        # Session & User Recently Viewed Tracking (fault-tolerant)
        try:
            if not self.request.session.session_key:
                self.request.session.save()
            session_key = self.request.session.session_key

            if self.request.user.is_authenticated:
                RecentlyViewed.objects.update_or_create(
                    user=self.request.user,
                    movie=movie,
                    defaults={'session_key': session_key}
                )
            elif session_key:
                RecentlyViewed.objects.update_or_create(
                    session_key=session_key,
                    movie=movie,
                    defaults={'user': None}
                )
        except Exception:
            pass



        # Active shows for ticket booking
        shows = Show.objects.filter(
            movie=movie,
            start_time__gte=timezone.now()
        ).select_related('screen__theater', 'screen__theater__city').order_by('screen__theater__city', 'screen__theater__name', 'start_time')
        
        context['shows'] = shows
        
        # Similar movies (share same genres)
        context['similar_movies'] = Movie.objects.filter(
            genres__in=movie.genres.all()
        ).exclude(id=movie.id).select_related('language').prefetch_related('genres').distinct()[:4]

        # Personalized recommendations
        context['recommendations'] = get_personalized_recommendations(
            user=self.request.user if self.request.user.is_authenticated else None,
            session_key=session_key,
            limit=4
        )
        return context


class MovieCreateView(StaffRequiredMixin, CreateView):
    model = Movie
    form_class = MovieForm
    template_name = 'movies/movie_form.html'
    success_url = reverse_lazy('movies:discovery')

    def form_valid(self, form):
        messages.success(self.request, "Movie created successfully!")
        return super().form_valid(form)


class MovieUpdateView(StaffRequiredMixin, UpdateView):
    model = Movie
    form_class = MovieForm
    template_name = 'movies/movie_form.html'
    success_url = reverse_lazy('movies:discovery')

    def form_valid(self, form):
        messages.success(self.request, "Movie updated successfully!")
        return super().form_valid(form)


class MovieDeleteView(StaffRequiredMixin, DeleteView):
    model = Movie
    template_name = 'movies/movie_confirm_delete.html'
    success_url = reverse_lazy('movies:discovery')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Movie deleted successfully.")
        return super().delete(request, *args, **kwargs)


class MovieAPIDiscoveryView(View):
    """
    REST API endpoint for movie discovery with dynamic search, multi-facet filters, sorting, and pagination.
    GET /api/movies/
    """
    def get(self, request):
        from django.http import JsonResponse
        from django.core.paginator import Paginator
        from .tmdb_service import get_safe_youtube_embed_url

        qs = Movie.objects.filter(is_active=True).select_related('language').prefetch_related('genres').annotate(
            min_price=Min('shows__base_price'),
            max_price=Max('shows__base_price')
        )

        search_query = request.GET.get('search') or request.GET.get('q', '').strip()
        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(director__icontains=search_query)
            )

        genre_id = request.GET.get('genre')
        if genre_id:
            qs = qs.filter(Q(genres__id=genre_id) | Q(genres__slug=genre_id) | Q(genres__name__iexact=genre_id))

        language_id = request.GET.get('language')
        if language_id:
            qs = qs.filter(Q(language__id=language_id) | Q(language__code=language_id) | Q(language__name__iexact=language_id))

        city = request.GET.get('city')
        if city:
            qs = qs.filter(Q(shows__screen__theater__city__id=city) | Q(shows__screen__theater__city__name__iexact=city))

        theater = request.GET.get('theater')
        if theater:
            qs = qs.filter(shows__screen__theater__id=theater)

        rating_min = request.GET.get('rating_min') or request.GET.get('rating')
        if rating_min:
            try:
                qs = qs.filter(rating__gte=float(rating_min))
            except ValueError:
                pass

        sort_by = request.GET.get('sort', 'popularity')
        if sort_by == 'newest':
            qs = qs.order_by('-release_date', '-popularity')
        elif sort_by == 'rating':
            qs = qs.order_by('-rating', '-popularity')
        elif sort_by == 'price_low':
            qs = qs.order_by('min_price', '-popularity')
        elif sort_by == 'price_high':
            qs = qs.order_by('-max_price', '-popularity')
        else:
            qs = qs.order_by('-popularity', '-rating')

        qs = qs.distinct()
        total_count = qs.count()

        page_number = request.GET.get('page', 1)
        paginator = Paginator(qs, 10)
        page_obj = paginator.get_page(page_number)

        results = []
        for movie in page_obj.object_list:
            results.append({
                'id': movie.id,
                'title': movie.title,
                'slug': movie.slug,
                'category': movie.category,
                'certificate': movie.certificate,
                'duration': movie.duration,
                'duration_formatted': movie.formatted_duration,
                'release_date': movie.release_date.isoformat() if movie.release_date else None,
                'rating': float(movie.rating),
                'popularity': movie.popularity,
                'poster_url': movie.get_poster_url,
                'backdrop_url': movie.get_backdrop_url,
                'trailer_embed_url': get_safe_youtube_embed_url(movie.trailer_url),
                'language': movie.language.name,
                'genres': [g.name for g in movie.genres.all()],
            })

        return JsonResponse({
            'count': total_count,
            'page': page_obj.number,
            'total_pages': paginator.num_pages,
            'next': page_obj.next_page_number() if page_obj.has_next() else None,
            'previous': page_obj.previous_page_number() if page_obj.has_previous() else None,
            'results': results
        })


class MovieSuggestionsAPIView(View):
    """
    REST API endpoint for fast live movie search suggestions & autocomplete.
    GET /api/movies/suggestions/?q=<query>&limit=8
    """
    def get(self, request):
        from django.http import JsonResponse
        from django.urls import reverse

        ensure_movies_seeded()

        query = request.GET.get('q', '').strip()
        try:
            limit = min(int(request.GET.get('limit', 8)), 20)
        except (ValueError, TypeError):
            limit = 8

        active_shows_subquery = Show.objects.filter(
            movie=OuterRef('pk'),
            start_time__gte=timezone.now(),
            status='OPEN'
        )

        qs = Movie.objects.filter(is_active=True)\
            .annotate(has_active_shows=Exists(active_shows_subquery))\
            .select_related('language').prefetch_related('genres')

        if query:
            qs = qs.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(director__icontains=query) |
                Q(genres__name__icontains=query) |
                Q(language__name__icontains=query)
            ).distinct().order_by('-popularity', '-rating')
        else:
            # Return top trending / popular suggestions when query is empty
            qs = qs.order_by('-popularity', '-rating')

        results = []
        for movie in qs[:limit]:
            results.append({
                'id': movie.id,
                'title': movie.title,
                'slug': movie.slug,
                'url': reverse('movies:detail', kwargs={'slug': movie.slug}),
                'poster_url': movie.get_poster_url,
                'backdrop_url': movie.get_backdrop_url,
                'rating': float(movie.rating) if movie.rating else 0.0,
                'release_year': movie.release_date.year if movie.release_date else None,
                'language': movie.language.name if movie.language else '',
                'genres': [g.name for g in movie.genres.all()[:2]],
                'duration_formatted': movie.formatted_duration,
                'has_active_shows': bool(movie.has_active_shows),
                'category': movie.category,
                'tagline': movie.tagline,
            })

        return JsonResponse({
            'status': 'success',
            'query': query,
            'count': len(results),
            'suggestions': results,
        })

