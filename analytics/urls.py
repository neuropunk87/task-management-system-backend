from django.urls import path
from analytics.views import AnalyticsView, ProjectAnalyticsChartView


urlpatterns = [
    path('<int:project_id>/', AnalyticsView.as_view(), name='project-analytics'),
]
