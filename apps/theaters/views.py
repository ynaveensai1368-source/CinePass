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
        return Theater.objects.filter(is_active=True).select_related('city').prefetch_related('screens')

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
