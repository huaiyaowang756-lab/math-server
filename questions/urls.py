from django.urls import path

from . import views, views_knowledge

urlpatterns = [
    path("formula/recognize/", views.recognize_formula, name="recognize_formula"),
    path("formula/recognize-url/", views.recognize_formula_url, name="recognize_formula_url"),
    path("upload/", views.upload_docx, name="upload_docx"),
    path("upload/tasks/", views.list_upload_tasks, name="list_upload_tasks"),
    path("upload/tasks/<str:task_id>/", views.get_or_delete_upload_task, name="upload_task_detail"),
    path("questions/save/", views.save_questions, name="save_questions"),
    path("questions/", views.list_questions, name="list_questions"),
    path("questions/export/", views.export_questions, name="export_questions"),
    path("questions/batch/", views.delete_batch, name="delete_batch"),
    path("questions/<str:question_id>/", views.get_question, name="get_question"),
    path("questions/<str:question_id>/update/", views.update_question, name="update_question"),
    path("questions/<str:question_id>/delete/", views.delete_question, name="delete_question"),
    # 知识管理
    path("knowledge/tree/", views_knowledge.knowledge_tree, name="knowledge_tree"),
    path("knowledge/categories/", views_knowledge.list_categories, name="knowledge_list_categories"),
    path("knowledge/categories/create/", views_knowledge.create_category, name="knowledge_create_category"),
    path("knowledge/categories/<str:category_id>/", views_knowledge.get_category, name="knowledge_get_category"),
    path("knowledge/categories/<str:category_id>/update/", views_knowledge.update_category, name="knowledge_update_category"),
    path("knowledge/categories/<str:category_id>/delete/", views_knowledge.delete_category, name="knowledge_delete_category"),
    path("knowledge/nodes/", views_knowledge.list_nodes, name="knowledge_list_nodes"),
    path("knowledge/nodes/create/", views_knowledge.create_node, name="knowledge_create_node"),
    path("knowledge/nodes/<str:node_id>/", views_knowledge.get_node, name="knowledge_get_node"),
    path("knowledge/nodes/<str:node_id>/update/", views_knowledge.update_node, name="knowledge_update_node"),
    path("knowledge/nodes/<str:node_id>/delete/", views_knowledge.delete_node, name="knowledge_delete_node"),
]
