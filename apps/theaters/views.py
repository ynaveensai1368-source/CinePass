from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy

from .models import City, Theater
from shows.models import Show
from .forms import TheaterForm, ShowForm, CityForm

class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

class TheaterListView(ListView):
    model = Theater
    template_name = 'theaters/theater_list.html'
    context_object_name = 'theaters'

    def get_queryset(self):
        city_param = self.request.GET.get('city')
        qs = Theater.objects.filter(is_active=True).select_related('city').prefetch_related('screens')
        
        if city_param:
            if str(city_param).isdigit():
                qs = qs.filter(city_id=int(city_param))
            else:
                qs = qs.filter(city__slug=city_param)
        else:
            session_city_id = self.request.session.get('selected_city_id')
            if session_city_id:
                # Prioritize theaters in active session city first
                qs = qs.filter(city_id=session_city_id)
                if not qs.exists():
                    qs = Theater.objects.filter(is_active=True).select_related('city').prefetch_related('screens')

        return qs.order_by('city__name', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cities'] = City.objects.filter(theaters__isnull=False).distinct().order_by('name')
        context['selected_city_filter'] = self.request.GET.get('city', '')
        return context

class TheaterCreateView(StaffRequiredMixin, CreateView):
    model = Theater
    form_class = TheaterForm
    template_name = 'theaters/theater_form.html'
    success_url = reverse_lazy('theaters:list')

class ShowCreateView(StaffRequiredMixin, CreateView):
    model = Show
    form_class = ShowForm
    template_name = 'theaters/show_form.html'
    success_url = reverse_lazy('theaters:list')
