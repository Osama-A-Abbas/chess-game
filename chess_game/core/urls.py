from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("game/<uuid:game_id>/", views.game_page, name="game_page"),
    path("game/<uuid:game_id>/state/", views.state, name="game_state"),
    path("game/<uuid:game_id>/legal/", views.legal, name="game_legal"),
    path("game/<uuid:game_id>/move/", views.move, name="game_move"),
]
