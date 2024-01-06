from django.urls import path, re_path
from django.conf import settings
from django.urls.conf import include
from dj_rest_auth.views import (
    PasswordChangeView,
    PasswordResetView, PasswordResetConfirmView)
import django_rest_passwordreset

from iam.views import (
    RulesView
)

urlpatterns = [
    path('rules', RulesView.as_view(), name='rules'),
]

if settings.IAM_TYPE == 'BASIC':
    urlpatterns += [
        path('password/reset', include('django_rest_passwordreset.urls', namespace='password_reset')),
        path('password/change', PasswordChangeView.as_view(),
             name='rest_password_change'),
        
    ]

urlpatterns = [path('auth/', include(urlpatterns))]
