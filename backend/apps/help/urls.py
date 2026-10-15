from django.urls import path

from .views import HelpArticleView, HelpListView

urlpatterns = [
    path("help", HelpListView.as_view(), name="help"),
    path("help/<slug:slug>", HelpArticleView.as_view(), name="help-article"),
]
