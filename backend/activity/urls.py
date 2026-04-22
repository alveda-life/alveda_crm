from django.urls import path

from .views import (
    ActivityHeatmapView,
    ActivityIngestView,
    ActivitySummaryView,
    ActivityTimelineView,
)


urlpatterns = [
    path('events/',   ActivityIngestView.as_view(),  name='activity-events'),
    path('summary/',  ActivitySummaryView.as_view(), name='activity-summary'),
    path('timeline/', ActivityTimelineView.as_view(), name='activity-timeline'),
    path('heatmap/',  ActivityHeatmapView.as_view(), name='activity-heatmap'),
]
