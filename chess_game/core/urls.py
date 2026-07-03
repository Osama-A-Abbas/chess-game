from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("accounts/signup/", views.signup, name="signup"),
    path("game/<uuid:game_id>/", views.game_page, name="game_page"),
    path("game/<uuid:game_id>/join/", views.join_game, name="game_join"),
    path("game/<uuid:game_id>/state/", views.state, name="game_state"),
    path("game/<uuid:game_id>/legal/", views.legal, name="game_legal"),
    path("game/<uuid:game_id>/move/", views.move, name="game_move"),
]
