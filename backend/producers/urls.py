from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    ProducerViewSet, ProducerTaskViewSet, ProducerStatsView, ProducerAnalyticsView,
    ProducerWeeklyReportViewSet,
)

router = DefaultRouter()
router.register(r'producers',      ProducerViewSet,     basename='producer')
router.register(r'producer-tasks', ProducerTaskViewSet, basename='producer-task')
router.register(r'producer-weekly-reports', ProducerWeeklyReportViewSet, basename='producer-weekly-report')

urlpatterns = [
    path('producers/stats/',     ProducerStatsView.as_view(),     name='producer-stats'),
    path('producers/analytics/', ProducerAnalyticsView.as_view(), name='producer-analytics'),
] + list(router.urls)
