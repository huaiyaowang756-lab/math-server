from django.urls import path

from . import views, views_knowledge, views_documents, views_tags, views_question_types
from . import views_recommend, views_ops, views_llm

urlpatterns = [
    path("formula/recognize/", views.recognize_formula, name="recognize_formula"),
    path("formula/recognize-url/", views.recognize_formula_url, name="recognize_formula_url"),
    # 标签管理（难度、分类、地区、场景）
    path("tags/", views_tags.list_tags, name="list_tags"),
    path("tags/create/", views_tags.create_tag, name="create_tag"),
    path("tags/<str:tag_id>/update/", views_tags.update_tag, name="update_tag"),
    path("tags/<str:tag_id>/delete/", views_tags.delete_tag, name="delete_tag"),
    path("tags/sort/", views_tags.batch_sort_tags, name="batch_sort_tags"),
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
    path("questions/recommend/", views_recommend.recommend, name="questions_recommend"),
    path("questions/", views.list_questions, name="list_questions"),
    path("questions/export/", views.export_questions, name="export_questions"),
    path("questions/batch/", views.delete_batch, name="delete_batch"),
    path("questions/<str:question_id>/", views.get_question, name="get_question"),
    path("questions/<str:question_id>/update/", views.update_question, name="update_question"),
    path("questions/<str:question_id>/delete/", views.delete_question, name="delete_question"),
    # 知识管理（统一知识节点树）
    path("knowledge/tree/", views_knowledge.knowledge_tree, name="knowledge_tree"),
    path("knowledge/nodes/search/", views_knowledge.search_nodes, name="knowledge_search_nodes"),
    path("knowledge/nodes/batch/", views_knowledge.batch_get_nodes, name="knowledge_batch_nodes"),
    path("knowledge/nodes/sort/", views_knowledge.batch_sort_nodes, name="knowledge_sort_nodes"),
    path("knowledge/nodes/create/", views_knowledge.create_node, name="knowledge_create_node"),
    path("knowledge/nodes/", views_knowledge.list_nodes, name="knowledge_list_nodes"),
    path("knowledge/nodes/<str:node_id>/", views_knowledge.get_node, name="knowledge_get_node"),
    path("knowledge/nodes/<str:node_id>/update/", views_knowledge.update_node, name="knowledge_update_node"),
    path("knowledge/nodes/<str:node_id>/delete/", views_knowledge.delete_node, name="knowledge_delete_node"),
    # 题型管理（题型节点树 + 绑定题目）
    path("question-types/tree/", views_question_types.question_type_tree, name="question_type_tree"),
    path("question-types/nodes/flat/", views_question_types.list_all_flat, name="question_type_nodes_flat"),
    path("question-types/nodes/sort/", views_question_types.batch_sort_nodes, name="question_type_sort_nodes"),
    path("question-types/nodes/create/", views_question_types.create_node, name="question_type_create_node"),
    path("question-types/nodes/", views_question_types.list_nodes, name="question_type_list_nodes"),
    path("question-types/nodes/<str:node_id>/", views_question_types.get_node, name="question_type_get_node"),
    path("question-types/nodes/<str:node_id>/update/", views_question_types.update_node, name="question_type_update_node"),
    path("question-types/nodes/<str:node_id>/delete/", views_question_types.delete_node, name="question_type_delete_node"),
    path("question-types/nodes/<str:node_id>/bind-questions/", views_question_types.bind_questions, name="question_type_bind_questions"),
    path("question-types/nodes/<str:node_id>/bound-ids/", views_question_types.bound_question_ids, name="question_type_bound_ids"),
    # 运维
    path("ops/build-vectors/", views_ops.build_vectors, name="ops_build_vectors"),
    # 大模型管理
    path("llm-models/", views_llm.list_llm_models, name="llm_models_list"),
    path("llm-models/create/", views_llm.create_llm_model, name="llm_models_create"),
    path("llm-models/<str:model_id>/", views_llm.get_llm_model, name="llm_models_get"),
    path("llm-models/<str:model_id>/update/", views_llm.update_llm_model, name="llm_models_update"),
    path("llm-models/<str:model_id>/delete/", views_llm.delete_llm_model, name="llm_models_delete"),
]
