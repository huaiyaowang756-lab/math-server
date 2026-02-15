from django.urls import path

from . import views, views_knowledge, views_documents

urlpatterns = [
    path("formula/recognize/", views.recognize_formula, name="recognize_formula"),
    path("formula/recognize-url/", views.recognize_formula_url, name="recognize_formula_url"),
    # 试卷/文档管理
    path("documents/upload/", views_documents.upload_document, name="document_upload"),
    path("documents/", views_documents.list_documents, name="document_list"),
    path("documents/<str:doc_id>/", views_documents.get_document, name="document_detail"),
    path("documents/<str:doc_id>/update/", views_documents.update_document, name="document_update"),
    path("documents/<str:doc_id>/delete/", views_documents.delete_document, name="document_delete"),
    path("documents/<str:doc_id>/download/", views_documents.download_document, name="document_download"),
    path("documents/<str:doc_id>/preview-pdf/", views_documents.preview_document, name="document_preview"),
    path("documents/<str:doc_id>/parse/", views_documents.parse_document, name="document_parse"),
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
