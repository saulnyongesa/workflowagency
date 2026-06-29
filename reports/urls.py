from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("finance-settings/", views.admin_finance_settings, name="admin_finance_settings"),
    path("toggle-job-claims/", views.admin_toggle_job_claims, name="admin_toggle_job_claims"),
    path("jobs/", views.admin_jobs_manager, name="admin_jobs_manager"),
    path("jobs/new/", views.admin_job_form, name="admin_job_create"),
    path("jobs/<int:job_id>/edit/", views.admin_job_form, name="admin_job_edit"),
    path("users/", views.admin_users_manager, name="admin_users_manager"),
    path("products/", views.admin_products_manager, name="admin_products_manager"),
    path("products/new/", views.admin_product_form, name="admin_product_create"),
    path("products/<int:product_id>/edit/", views.admin_product_form, name="admin_product_edit"),
    path("content/", views.admin_content_manager, name="admin_content_manager"),
    path("content/<str:content_type>/<int:object_id>/edit/", views.admin_content_edit, name="admin_content_edit"),
    path("ledger-export.csv", views.export_ledger_csv, name="export_ledger_csv"),
]
