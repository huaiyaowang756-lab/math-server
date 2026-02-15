from django.urls import path

from . import views

urlpatterns = [
    path("formula/recognize/", views.recognize_formula, name="recognize_formula"),
    path("upload/", views.upload_docx, name="upload_docx"),
    path("questions/save/", views.save_questions, name="save_questions"),
    path("questions/", views.list_questions, name="list_questions"),
    path("questions/batch/", views.delete_batch, name="delete_batch"),
    path("questions/<str:question_id>/", views.get_question, name="get_question"),
    path("questions/<str:question_id>/update/", views.update_question, name="update_question"),
    path("questions/<str:question_id>/delete/", views.delete_question, name="delete_question"),
]
