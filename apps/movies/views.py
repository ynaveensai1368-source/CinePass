from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView

import datetime
import logging
from django.db.models import Q, Min, Max, Avg, Count, Exists, OuterRef, Case, When, Value, IntegerField
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


import threading

_seeding_lock = threading.Lock()
_seeded = False


def ensure_movies_seeded():
    """Defensive non-blocking helper ensuring database has latest 2026/2025 movie catalog populated."""
    global _seeded
    if _seeded:
        return
    if not _seeding_lock.acquire(blocking=False):
        return
    try:
        if Movie.objects.filter(title='Spider-Man: Brand New Day').exists() or Movie.objects.count() >= 10:
            _seeded = True
            _seeding_lock.release()
            return

        from .catalog import seed_production_catalog
        def _run_seed():
            try:
                logger.info("Initializing CinePass production movie catalog...")
                seed_production_catalog()
            except Exception as e:
                logger.warning(f"Catalog seeding notice: {e}")
            finally:
                try:
                    _seeding_lock.release()
                except RuntimeError:
                    pass

        threading.Thread(target=_run_seed, daemon=True).start()
        _seeded = True
    except Exception as e:
        logger.warning(f"Auto-seeding check notice: {e}")
        try:
            _seeding_lock.release()
        except RuntimeError:
            pass


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

        now = timezone.now()
        today = now.date()

        # 1. Resolve Active City (Single reliable source of truth)
        current_city = context.get('current_city')
        if not current_city:
            city_id = self.request.session.get('selected_city_id')
            if city_id:
                current_city = City.objects.filter(id=city_id).first()
        if not current_city:
            current_city = City.objects.filter(theaters__isnull=False).first() or City.objects.first()

        # 2. City-Aware Active Shows Subquery
        if current_city:
            city_shows_subquery = Show.objects.filter(
                movie=OuterRef('pk'),
                screen__theater__city=current_city,
                start_time__gte=now,
                status='OPEN'
            )
        else:
            city_shows_subquery = Show.objects.filter(
                movie=OuterRef('pk'),
                start_time__gte=now,
                status='OPEN'
            )

        # Base optimized queryset
        base_movies = Movie.objects.filter(is_active=True)\
            .annotate(has_active_shows=Exists(city_shows_subquery))\
            .select_related('language').prefetch_related('genres')

        # 3. Regional Language Prominence for the Selected City
        from .recommendations import get_city_language_priority
        priority_langs = get_city_language_priority(current_city)
        lang_whens = [When(language__code=lcode, then=Value(100 - (i * 15))) for i, lcode in enumerate(priority_langs)]
        lang_priority_case = Case(*lang_whens, default=Value(10), output_field=IntegerField())

        # 4. Now Playing in Theaters: Specifically movies currently running in the user's selected city!
        if current_city:
            now_playing_city_qs = base_movies.filter(
                has_active_shows=True
            ).annotate(
                lang_priority=lang_priority_case
            ).order_by('-lang_priority', '-release_date', '-popularity')[:8]

            # If city has fewer than 6 active theatrical shows, supplement with general theatrical releases
            now_playing_list = list(now_playing_city_qs)
            if len(now_playing_list) < 6:
                existing_ids = {m.id for m in now_playing_list}
                supplemental_qs = base_movies.filter(
                    Q(category='now_playing') | Q(release_date__gte=today - datetime.timedelta(days=90))
                ).exclude(id__in=existing_ids).annotate(
                    lang_priority=lang_priority_case
                ).order_by('-lang_priority', '-release_date', '-popularity')[:(8 - len(now_playing_list))]
                now_playing_list.extend(list(supplemental_qs))
            now_playing_qs = now_playing_list
        else:
            now_playing_qs = list(base_movies.filter(
                Q(category='now_playing') | Q(has_active_shows=True)
            ).order_by('-release_date', '-popularity')[:8])

        context['now_playing'] = now_playing_qs

        # 5. Hero Banner Carousel: High-res backdrops of top movies available in current city or top blockbusters
        hero_movies = [m for m in now_playing_qs if m.backdrop_url][:5]
        if not hero_movies:
            hero_movies = list(base_movies.filter(release_date__year__gte=2024).exclude(backdrop_url__isnull=True).exclude(backdrop_url='').order_by('-popularity')[:5])
        context['hero_movies'] = hero_movies

        # 6. Personalized & Location Recommendations (BookMyShow discovery hierarchy)
        context['recommended_movies'] = get_personalized_recommendations(
            user=self.request.user if self.request.user.is_authenticated else None,
            session_key=session_key,
            city=current_city,
            limit=6
        )

        context['popular_movies'] = base_movies.annotate(lang_priority=lang_priority_case).order_by('-has_active_shows', '-lang_priority', '-popularity', '-rating')[:6]
        context['top_rated_movies'] = base_movies.order_by('-rating', '-popularity')[:6]
        
        upcoming_qs = base_movies.filter(
            Q(category='upcoming') | Q(release_date__gt=today)
        ).order_by('release_date', '-popularity')[:6]
        if not upcoming_qs.exists():
            upcoming_qs = base_movies.order_by('-release_date')[:6]
        context['upcoming_movies'] = upcoming_qs

        # 7. Recently Viewed Movies
        rv_qs = RecentlyViewed.objects.none()
        if self.request.user.is_authenticated:
            rv_qs = RecentlyViewed.objects.filter(user=self.request.user)
        elif session_key:
            rv_qs = RecentlyViewed.objects.filter(session_key=session_key)

        context['recently_viewed'] = [
            rv.movie for rv in rv_qs.select_related('movie__language').prefetch_related('movie__genres')[:6]
        ]

        # 8. Real Languages Available with Active Screenings in this City
        if current_city:
            city_lang_ids = Show.objects.filter(
                screen__theater__city=current_city,
                start_time__gte=now,
                status='OPEN'
            ).values_list('movie__language_id', flat=True).distinct()
            context['city_languages'] = Language.objects.filter(id__in=city_lang_ids).order_by('name')
        else:
            context['city_languages'] = Language.objects.all().order_by('name')

        context['cities'] = City.objects.all()
        return context


class MovieDiscoveryView(ListView):
    model = Movie
    template_name = 'movies/movie_list.html'
    context_object_name = 'movies'
    paginate_by = 12

    def get_queryset(self):
        ensure_movies_seeded()
        now = timezone.now()
        today = now.date()

        # 1. Resolve Active City from Query Param or Session
        city_param = self.request.GET.get('city')
        city_obj = None
        if city_param:
            if str(city_param).isdigit():
                city_obj = City.objects.filter(id=int(city_param)).first()
            if not city_obj:
                city_obj = City.objects.filter(slug=city_param).first() or City.objects.filter(name__iexact=city_param).first()
            if city_obj:
                self.request.session['selected_city_id'] = city_obj.id
                self.request.session['selected_city_name'] = city_obj.name
                self.request.session['selected_city_slug'] = city_obj.slug
        else:
            city_id = self.request.session.get('selected_city_id')
            if city_id:
                city_obj = City.objects.filter(id=city_id).first()

        active_shows_subquery = None
        if city_obj:
            active_shows_subquery = Show.objects.filter(
                movie=OuterRef('pk'),
                screen__theater__city=city_obj,
                start_time__gte=now,
                status='OPEN'
            )
        else:
            active_shows_subquery = Show.objects.filter(
                movie=OuterRef('pk'),
                start_time__gte=now,
                status='OPEN'
            )

        qs = Movie.objects.filter(is_active=True)\
            .annotate(has_active_shows=Exists(active_shows_subquery))\
            .select_related('language').prefetch_related('genres').annotate(
                min_price=Min('shows__base_price'),
                max_price=Max('shows__base_price')
            )

        # 2. Search Query
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            qs = qs.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query) |
                Q(director__icontains=search_query)
            )

        # 3. Multi-Facet Filters
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category=category)

        genre_id = self.request.GET.get('genre')
        if genre_id:
            qs = qs.filter(genres__id=genre_id)

        language_id = self.request.GET.get('language')
        if language_id:
            if str(language_id).isdigit():
                qs = qs.filter(language__id=int(language_id))
            else:
                qs = qs.filter(Q(language__code=language_id) | Q(language__name__iexact=language_id))

        theater_id = self.request.GET.get('theater')
        if theater_id and str(theater_id).isdigit():
            qs = qs.filter(shows__screen__theater__id=int(theater_id), shows__start_time__gte=now, shows__status='OPEN')
        elif city_param:
            # When user explicitly filters by a specific city, show movies having shows in that city
            if city_obj:
                qs = qs.filter(shows__screen__theater__city=city_obj, shows__start_time__gte=now, shows__status='OPEN')

        min_rating = self.request.GET.get('rating')
        if min_rating:
            try:
                qs = qs.filter(rating__gte=float(min_rating))
            except ValueError:
                pass

        release_year = self.request.GET.get('release_date')
        if release_year:
            if release_year == 'upcoming':
                qs = qs.filter(release_date__gt=today)
            elif release_year == 'recent':
                qs = qs.filter(release_date__lte=today)

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

        # 4. Regional Language Prominence and Sorting Choice
        from .recommendations import get_city_language_priority
        priority_langs = get_city_language_priority(city_obj)
        lang_whens = [When(language__code=lcode, then=Value(100 - (i * 15))) for i, lcode in enumerate(priority_langs)]
        lang_priority_case = Case(*lang_whens, default=Value(10), output_field=IntegerField())

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
            # BookMyShow-like default ranking: City Showtimes -> Regional Language Fit -> Popularity -> Rating
            qs = qs.annotate(lang_priority=lang_priority_case).order_by('-has_active_shows', '-lang_priority', '-popularity', '-rating')

        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Determine active city
        active_city = context.get('current_city')
        city_param = self.request.GET.get('city')
        if city_param:
            if str(city_param).isdigit():
                active_city = City.objects.filter(id=int(city_param)).first()
            if not active_city:
                active_city = City.objects.filter(slug=city_param).first() or City.objects.filter(name__iexact=city_param).first()

        context['genres'] = Genre.objects.all().order_by('name')
        context['languages'] = Language.objects.all().order_by('name')
        context['cities'] = City.objects.filter(theaters__isnull=False).distinct().order_by('name')
        
        # Coupled Theaters: If city is selected, only show theaters located in that city!
        if active_city:
            context['theaters'] = Theater.objects.filter(city=active_city, is_active=True).order_by('name')
        else:
            context['theaters'] = Theater.objects.filter(is_active=True).select_related('city').order_by('name')
        
        context['current_search'] = self.request.GET.get('q', '')
        context['current_category'] = self.request.GET.get('category', '')
        context['current_genre'] = self.request.GET.get('genre', '')
        context['current_language'] = self.request.GET.get('language', '')
        context['current_city'] = str(active_city.id) if active_city else self.request.GET.get('city', '')
        context['current_theater'] = self.request.GET.get('theater', '')
        context['current_rating'] = self.request.GET.get('rating', '')
        context['current_sort'] = self.request.GET.get('sort', 'popularity')
        context['current_release'] = self.request.GET.get('release_date', '')
        context['current_show_time'] = self.request.GET.get('show_time', '')

        # Empty State Message Generation
        movie_count = self.get_queryset().count()
        context['movie_count'] = movie_count

        selected_lang_obj = None
        if context['current_language']:
            if str(context['current_language']).isdigit():
                selected_lang_obj = Language.objects.filter(id=int(context['current_language'])).first()
            else:
                selected_lang_obj = Language.objects.filter(Q(code=context['current_language']) | Q(name__iexact=context['current_language'])).first()

        if movie_count == 0:
            if selected_lang_obj and active_city:
                context['empty_title'] = f"No {selected_lang_obj.name} Movies in {active_city.name}"
                context['empty_message'] = f"There are currently no movies available in {selected_lang_obj.name} screening in {active_city.name}."
            elif active_city:
                context['empty_title'] = f"No Movies Found in {active_city.name}"
                context['empty_message'] = f"No movies match your selected filters in {active_city.name}."
            else:
                context['empty_title'] = "No Movies Found"
                context['empty_message'] = "Try adjusting your search keywords or filter criteria to find matching releases."

        get_copy = self.request.GET.copy()
        if 'page' in get_copy:
            del get_copy['page']
        context['querystring'] = get_copy.urlencode()

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
                if not movie.has_trailer:
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



        # 4. Active Shows & Multi-tier Hierarchical Grouping (City -> Theater -> Screen -> Shows)
        now = timezone.now()
        shows_qs = Show.objects.filter(
            movie=movie,
            start_time__gte=now,
            status='OPEN'
        ).select_related(
            'screen__theater__city',
            'screen__theater',
            'screen'
        ).order_by(
            'start_time',
            'screen__theater__city__name',
            'screen__theater__name',
            'screen__name'
        )

        # Extract unique available dates with active shows
        raw_dates = sorted(list({s.start_time.date() for s in shows_qs}))
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)

        available_dates = []
        for d in raw_dates:
            if d == today:
                day_name = 'Today'
            elif d == tomorrow:
                day_name = 'Tomorrow'
            else:
                day_name = d.strftime('%a')

            available_dates.append({
                'date': d,
                'date_str': d.strftime('%Y-%m-%d'),
                'day_name': day_name,
                'day_number': d.strftime('%d'),
                'month_name': d.strftime('%b'),
                'full_display': d.strftime('%A, %b %d, %Y')
            })

        # Selected Date logic
        selected_date_param = self.request.GET.get('date', '').strip()
        selected_date = None
        if selected_date_param:
            try:
                selected_date = datetime.datetime.strptime(selected_date_param, '%Y-%m-%d').date()
            except ValueError:
                selected_date = None

        if not selected_date and raw_dates:
            selected_date = raw_dates[0]

        # Extract all available cities for this movie
        available_cities = sorted(
            list({s.screen.theater.city for s in shows_qs}),
            key=lambda c: c.name
        )

        # Selected City logic: query param > active session city > all
        selected_city_param = self.request.GET.get('city', '').strip()
        if not selected_city_param:
            active_city = context.get('current_city')
            if active_city and any(c.id == active_city.id for c in available_cities):
                selected_city_param = str(active_city.id)

        # Filter shows by selected date & optional city
        day_filtered_shows = shows_qs
        if selected_date:
            day_filtered_shows = day_filtered_shows.filter(start_time__date=selected_date)

        if selected_city_param:
            if selected_city_param.isdigit():
                day_filtered_shows = day_filtered_shows.filter(screen__theater__city_id=int(selected_city_param))
            else:
                day_filtered_shows = day_filtered_shows.filter(screen__theater__city__name__iexact=selected_city_param)

        # Group by Theater -> Screen -> Shows
        theaters_map = {}
        for s in day_filtered_shows:
            t = s.screen.theater
            scr = s.screen

            if t.id not in theaters_map:
                theaters_map[t.id] = {
                    'theater': t,
                    'city': t.city,
                    'screens': {}
                }

            if scr.id not in theaters_map[t.id]['screens']:
                theaters_map[t.id]['screens'][scr.id] = {
                    'screen': scr,
                    'screen_type_display': scr.get_screen_type_display(),
                    'shows': []
                }

            theaters_map[t.id]['screens'][scr.id]['shows'].append(s)

        grouped_theaters = []
        for t_data in theaters_map.values():
            screens_list = list(t_data['screens'].values())
            screens_list.sort(key=lambda x: (x['screen'].name))
            grouped_theaters.append({
                'theater': t_data['theater'],
                'city': t_data['city'],
                'screens': screens_list,
                'total_shows': sum(len(x['shows']) for x in screens_list)
            })

        # Order theaters by city name, then theater name
        grouped_theaters.sort(key=lambda x: (x['city'].name, x['theater'].name))

        context['available_dates'] = available_dates
        context['selected_date'] = selected_date
        context['selected_date_str'] = selected_date.strftime('%Y-%m-%d') if selected_date else ''
        context['available_cities'] = available_cities
        context['selected_city'] = selected_city_param
        context['grouped_theaters'] = grouped_theaters
        context['total_shows_count'] = day_filtered_shows.count()
        context['total_all_shows_count'] = shows_qs.count()
        context['shows'] = day_filtered_shows

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

        # Guarantee all movies have a valid language assigned
        from .models import Language
        def_lang = Language.objects.filter(code='en').first() or Language.objects.first()
        if def_lang:
            Movie.objects.filter(language__isnull=True).update(language=def_lang)

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
            ).distinct().order_by('-release_date', '-popularity')
        else:
            # Return latest 2026/2025 releases when query is empty
            qs = qs.filter(release_date__year__gte=2024).order_by('-release_date', '-popularity')
            if not qs.exists():
                qs = Movie.objects.filter(is_active=True).order_by('-release_date', '-popularity')

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

