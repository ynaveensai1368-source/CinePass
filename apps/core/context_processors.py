from theaters.models import City

# Top Indian Metro Cities for 1-click BookMyShow-style quick selection
POPULAR_CITY_NAMES = [
    'Hyderabad',
    'Mumbai',
    'Bengaluru',
    'Chennai',
    'Delhi-NCR',
    'Pune',
    'Kochi',
]

def location_context(request):
    """
    Global context processor providing the active user location and city directory.
    Enforces a single reliable source of truth across all views and templates.
    """
    all_cities = list(City.objects.filter(theaters__isnull=False).distinct().order_by('name'))
    if not all_cities:
        all_cities = list(City.objects.all().order_by('name'))

    selected_city = None

    # 1. Query parameter override (?city=... supports ID, slug, or name)
    city_param = request.GET.get('city')
    if city_param:
        city_param_str = str(city_param).strip()
        if city_param_str.isdigit():
            selected_city = next((c for c in all_cities if c.id == int(city_param_str)), None)
        if not selected_city:
            selected_city = next((c for c in all_cities if c.slug == city_param_str or c.name.lower() == city_param_str.lower()), None)
        if not selected_city:
            selected_city = City.objects.filter(id=city_param_str).first() if city_param_str.isdigit() else City.objects.filter(name__iexact=city_param_str).first()
        if selected_city:
            request.session['selected_city_id'] = selected_city.id
            request.session['selected_city_name'] = selected_city.name
            request.session['selected_city_slug'] = selected_city.slug

    # 2. Session storage
    if not selected_city and 'selected_city_id' in request.session:
        session_id = request.session.get('selected_city_id')
        selected_city = next((c for c in all_cities if c.id == session_id), None)
        if not selected_city:
            selected_city = City.objects.filter(id=session_id).first()

    # 3. Cookie storage
    if not selected_city and 'cinepass_city_id' in request.COOKIES:
        cookie_id = request.COOKIES.get('cinepass_city_id')
        if cookie_id and str(cookie_id).isdigit():
            selected_city = next((c for c in all_cities if c.id == int(cookie_id)), None)
            if not selected_city:
                selected_city = City.objects.filter(id=int(cookie_id)).first()

    # 4. Default fallback: Default to Hyderabad, Mumbai, or first available city
    if not selected_city:
        selected_city = next((c for c in all_cities if c.name.lower() == 'hyderabad'), None)
        if not selected_city:
            selected_city = next((c for c in all_cities if c.name.lower() == 'mumbai'), None)
        if not selected_city and all_cities:
            selected_city = all_cities[0]

    # Save to session if resolved
    if selected_city and request.session.get('selected_city_id') != selected_city.id:
        request.session['selected_city_id'] = selected_city.id
        request.session['selected_city_name'] = selected_city.name
        request.session['selected_city_slug'] = selected_city.slug

    # Segregate popular cities in order
    popular_cities = []
    popular_set = set()
    for pname in POPULAR_CITY_NAMES:
        c_obj = next((c for c in all_cities if c.name.lower() == pname.lower()), None)
        if c_obj:
            popular_cities.append(c_obj)
            popular_set.add(c_obj.id)

    other_cities = [c for c in all_cities if c.id not in popular_set]

    return {
        'current_city': selected_city,
        'current_city_id': selected_city.id if selected_city else None,
        'current_city_name': selected_city.name if selected_city else 'Select City',
        'all_cities': all_cities,
        'popular_cities': popular_cities,
        'other_cities': other_cities,
    }
