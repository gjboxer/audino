from django.urls import path
from django.urls.conf import include
from rest_framework.routers import DefaultRouter
from .views import *
from .views import ProjectViewSet

router = DefaultRouter(trailing_slash=True)
router.register(r'projects', ProjectViewSet)
router.register(r'labels', LabelViewSet)
router.register(r'tasks', TaskViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path("tasks/<task_id>/data", add_data, name="add_data"),
    path("jobs", jobs, name="jobs"),
    path("jobs/<job_id>", get_job_by_id, name="get_job_by_id"),
    path("jobs/<job_id>/annotation", job_annotation, name="job_annotation"),
    path("jobs/<job_id>/annotation/<a_id>", annotations, name="annotations"),
]
