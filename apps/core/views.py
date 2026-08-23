import math
import json
from django.http import JsonResponse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from theaters.models import City, Theater
from movies.models import Language, Movie
from shows.models import Show
from django.utils import timezone

# Known Coordinates Reference for Indian Metro and Major Cities
CITY_CENTROIDS = {
    'hyderabad': (17.385044, 78.486671),
    'mumbai': (19.075983, 72.877655),
    'bengaluru': (12.971599, 77.594566),
    'chennai': (13.082680, 80.270721),
    'delhi-ncr': (28.613939, 77.209023),
    'pune': (18.520430, 73.856743),
    'kochi': (9.931233, 76.267303),
    'kolkata': (22.572645, 88.363892),
    'ahmedabad': (23.022505, 72.571365),
    'jaipur': (26.912434, 75.787270),
    'chandigarh': (30.733315, 76.779419),
}

def _haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def health_check(request):
    """
    Production health check endpoint verifying database connectivity.
    GET /api/health/
    """
    db_status = "ok"
    try:
        connection.ensure_connection()
    except Exception:
        db_status = "error"

    status_code = 200 if db_status == "ok" else 500
    return JsonResponse({
        "status": "ok" if db_status == "ok" else "error",
        "database": db_status,
        "version": "1.0.0"
    }, status=status_code)


def _extract_request_data(request):
    """Safely extracts parameters from GET, POST, or JSON body without RawPostDataException."""
    data = {}
    if request.GET:
        data.update(request.GET.dict())
    
    content_type = request.META.get('CONTENT_TYPE', '')
    if 'application/json' in content_type:
        try:
            if request.body:
                data.update(json.loads(request.body.decode('utf-8')))
        except Exception:
            pass
    elif request.POST:
        data.update(request.POST.dict())
    
    return data


@csrf_exempt
@require_http_methods(["GET", "POST"])
def set_location_api(request):
    """
    API endpoint to set the active user city globally.
    Saves in session and sets persistent cookie.
    POST/GET /api/location/set/?city_id=1
    """
    params = _extract_request_data(request)
    city_id = params.get('city_id')
    city_slug = params.get('city_slug')
    city_name = params.get('city_name')

    city = None
    if city_id and str(city_id).isdigit():
        city = City.objects.filter(id=int(city_id)).first()
    elif city_slug:
        city = City.objects.filter(slug=city_slug).first() or City.objects.filter(name__iexact=city_slug).first()
    elif city_name:
        city = City.objects.filter(name__iexact=city_name).first()

    if not city:
        return JsonResponse({
            'status': 'error',
            'message': 'City not found.'
        }, status=404)

    # Save to session
    request.session['selected_city_id'] = city.id
    request.session['selected_city_name'] = city.name
    request.session['selected_city_slug'] = city.slug

    response = JsonResponse({
        'status': 'success',
        'city': {
            'id': city.id,
            'name': city.name,
            'slug': city.slug,
            'state': city.state
        }
    })
    # Set 30-day persistent cookie
    response.set_cookie('cinepass_city_id', str(city.id), max_age=30 * 24 * 60 * 60, samesite='Lax')
    return response


@csrf_exempt
@require_http_methods(["GET", "POST"])
def detect_location_api(request):
    """
    API endpoint for 'Detect my location'. Accepts lat/lon from browser geolocation,
    computes closest supported CinePass city via Haversine distance, and activates it.
    POST/GET /api/location/detect/?lat=17.4&lng=78.5
    """
    params = _extract_request_data(request)
    lat = params.get('lat') or params.get('latitude')
    lng = params.get('lng') or params.get('longitude')

    try:
        user_lat = float(lat)
        user_lng = float(lng)
    except (TypeError, ValueError):
        return JsonResponse({
            'status': 'error',
            'message': 'Valid latitude and longitude are required.'
        }, status=400)

    cities = list(City.objects.all())

    if not cities:
        return JsonResponse({'status': 'error', 'message': 'No cities configured.'}, status=404)

    best_city = None
    min_dist = float('inf')

    for c in cities:
        c_lat, c_lng = None, None
        if hasattr(c, 'latitude') and getattr(c, 'latitude', None):
            try:
                c_lat = float(c.latitude)
                c_lng = float(c.longitude)
            except Exception:
                c_lat, c_lng = None, None

        if c_lat is None or c_lng is None:
            c_key = c.name.lower().replace(' ', '-')
            if c_key in CITY_CENTROIDS:
                c_lat, c_lng = CITY_CENTROIDS[c_key]
            else:
                for k, coords in CITY_CENTROIDS.items():
                    if k in c_key or c_key in k:
                        c_lat, c_lng = coords
                        break

        if c_lat is not None and c_lng is not None:
            dist = _haversine_distance(user_lat, user_lng, c_lat, c_lng)
            if dist < min_dist:
                min_dist = dist
                best_city = c

    if not best_city:
        best_city = cities[0]

    request.session['selected_city_id'] = best_city.id
    request.session['selected_city_name'] = best_city.name
    request.session['selected_city_slug'] = best_city.slug

    response = JsonResponse({
        'status': 'success',
        'city': {
            'id': best_city.id,
            'name': best_city.name,
            'slug': best_city.slug,
            'state': best_city.state,
            'distance_km': round(min_dist, 1) if min_dist != float('inf') else None
        }
    })
    response.set_cookie('cinepass_city_id', str(best_city.id), max_age=30 * 24 * 60 * 60, samesite='Lax')
    return response


def get_theaters_by_city_api(request):
    """
    API endpoint returning theaters for a specific city to power coupled dropdown filters.
    GET /api/theaters-by-city/?city_id=1
    """
    city_id = request.GET.get('city_id')
    theaters_qs = Theater.objects.filter(is_active=True)
    if city_id and str(city_id).isdigit():
        theaters_qs = theaters_qs.filter(city_id=int(city_id))
    elif city_id:
        theaters_qs = theaters_qs.filter(city__slug=city_id)

    theaters_data = [
        {'id': t.id, 'name': t.name, 'city_id': t.city_id, 'city_name': t.city.name}
        for t in theaters_qs.select_related('city').order_by('name')
    ]
    return JsonResponse({'status': 'success', 'theaters': theaters_data})


def get_city_languages_api(request):
    """
    API endpoint returning languages with active movie screenings in a specific city.
    GET /api/languages-by-city/?city_id=1
    """
    city_id = request.GET.get('city_id')
    now = timezone.now()

    shows_qs = Show.objects.filter(start_time__gte=now, status='OPEN')
    if city_id and str(city_id).isdigit():
        shows_qs = shows_qs.filter(screen__theater__city_id=int(city_id))

    city_show_langs = shows_qs.values_list('language_id', 'movie__language_id')
    lang_ids = set()
    for l_id, ml_id in city_show_langs:
        if l_id:
            lang_ids.add(l_id)
        elif ml_id:
            lang_ids.add(ml_id)

    languages = Language.objects.filter(id__in=lang_ids).order_by('name')
    langs_data = [{'id': l.id, 'name': l.name, 'code': l.code} for l in languages]
    return JsonResponse({'status': 'success', 'languages': langs_data})
