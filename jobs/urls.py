from django.urls import path

from . import views

urlpatterns = [
    path("", views.job_list, name="job_list"),
    path("mine/", views.my_jobs, name="my_jobs"),
    path("review/", views.review_queue, name="review_queue"),
    path("review/<int:submission_id>/approve/", views.approve_submission_view, name="approve_submission"),
    path("review/<int:submission_id>/reject/", views.reject_submission_view, name="reject_submission"),
    path("admin/clone/<int:job_id>/", views.clone_job_view, name="clone_job"),
    path("claim/<int:claim_id>/submit/", views.submit_job, name="submit_job"),
    path("submission/<int:submission_id>/", views.job_submission_detail, name="job_submission_detail"),
    path("<slug:slug>/claim/", views.claim_job_view, name="claim_job"),
    path("<slug:slug>/", views.job_detail, name="job_detail"),
]
