

from django.conf.urls import include, url

from qatrack.qatrack_core import views

urlpatterns = [
    url(r"^comment/ajax_comment/$", views.ajax_comment, name='ajax_comment'),
]