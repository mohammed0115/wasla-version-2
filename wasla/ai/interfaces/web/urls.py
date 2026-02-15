from django.urls import path

from . import views


urlpatterns = [
    path("dashboard/ai/tools", views.ai_tools, name="dashboard_ai_tools"),
    path(
        "dashboard/ai/description/<int:product_id>",
        views.ai_generate_description,
        name="dashboard_ai_description",
    ),
    path(
        "dashboard/ai/categorize/<int:product_id>",
        views.ai_categorize_product,
        name="dashboard_ai_categorize",
    ),
    path("dashboard/ai/visual-search", views.ai_visual_search, name="dashboard_ai_visual_search"),
]
