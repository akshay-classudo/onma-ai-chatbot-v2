from django.urls import path

from . import views

urlpatterns = [
    path("api/session/", views.session_create, name="session_create"),
    path("api/session/<str:session_token>/", views.session_erase, name="session_erase"),
    path("api/chat/", views.chat, name="chat"),
    path("api/chat/stream/", views.chat_stream, name="chat_stream"),
    path("api/lead/", views.lead_create, name="lead_create"),
    path("api/config/", views.public_config, name="public_config"),
    path("demo/", views.demo, name="demo"),
]
