from django.urls import path
from django.urls.conf import include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter(trailing_slash=True)
router.register(r'projects', ProjectViewSet)
router.register(r'labels', LabelViewSet)
router.register(r'tasks', TaskViewSet)
router.register(r'jobs', JobViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path("tasks/<task_id>/data", add_data, name="add_data"),
    path("jobs/<job_id>/annotation", job_annotation, name="job_annotation"),
    path("jobs/<int:job_id>/annotation/<int:a_id>", AnnotationViewSet.as_view({'get': 'list', 'patch': 'perform_update', 'delete': 'perform_destroy'}), name="annotations"),
]
