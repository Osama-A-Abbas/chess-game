from django.urls import path

from . import views

urlpatterns = [
    path("match/find/", views.find_match, name="find_match"),
    path("match/cancel/", views.cancel_match, name="cancel_match"),
]
