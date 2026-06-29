from django.urls import path

from . import views

urlpatterns = [
    path("", views.support_center, name="support_center"),
    path("tickets/", views.support_ticket_list, name="support_ticket_list"),
    path("tickets/new/", views.support_ticket_create, name="support_ticket_create"),
    path("tickets/<int:pk>/", views.support_ticket_detail, name="support_ticket_detail"),
    path("admin/tickets/", views.support_ticket_queue, name="support_ticket_queue"),
    path("policies/", views.policy_list, name="policy_list"),
    path("policies/<slug:slug>/", views.policy_detail, name="policy_detail"),
    path("faq/", views.faq_list, name="faq_list"),
]
