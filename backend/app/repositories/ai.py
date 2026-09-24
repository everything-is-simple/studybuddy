"""稳定的 AI 检索、索引、嵌入和问答仓储域出口。"""

from . import _legacy_part_00 as _part_00
from . import _legacy_part_14 as _part_14
from . import _legacy_part_15 as _part_15
from . import _legacy_part_16 as _part_16
from . import _legacy_part_17 as _part_17

RETRIEVAL_POLICY_VERSION = _part_00.RETRIEVAL_POLICY_VERSION
CONTEXT_ASSEMBLER_POLICY_VERSION = _part_00.CONTEXT_ASSEMBLER_POLICY_VERSION
MAX_CONTEXT_TOKENS = _part_00.MAX_CONTEXT_TOKENS
CITATION_KEY_PREFIX = _part_00.CITATION_KEY_PREFIX
MAX_RETRIEVAL_QUERY_LENGTH = _part_00.MAX_RETRIEVAL_QUERY_LENGTH
MAX_RETRIEVAL_TOP_K = _part_00.MAX_RETRIEVAL_TOP_K
VECTOR_POLICY_VERSION = _part_00.VECTOR_POLICY_VERSION
HYBRID_POLICY_VERSION = _part_00.HYBRID_POLICY_VERSION
FALLBACK_LEXICAL_POLICY_VERSION = _part_00.FALLBACK_LEXICAL_POLICY_VERSION
RRF_K = _part_00.RRF_K
VECTOR_CANDIDATE_POOL = _part_00.VECTOR_CANDIDATE_POOL
MAX_QA_QUESTION_LENGTH = _part_00.MAX_QA_QUESTION_LENGTH
QA_PROMPT_VERSION = _part_00.QA_PROMPT_VERSION
QA_OPERATION_LEASE_SECONDS = _part_00.QA_OPERATION_LEASE_SECONDS
get_qa_citation_detail = _part_14.get_qa_citation_detail
list_qa_threads = _part_14.list_qa_threads
get_qa_thread_history = _part_14.get_qa_thread_history
create_or_get_revision = _part_14.create_or_get_revision
index_material_revision = _part_14.index_material_revision
reclaim_stale_embedding_operations = _part_14.reclaim_stale_embedding_operations
create_task_backed_embedding_operation = _part_14.create_task_backed_embedding_operation
get_operation_task_public = _part_15.get_operation_task_public
list_operation_tasks_public = _part_15.list_operation_tasks_public
create_embedding_index_operation = _part_15.create_embedding_index_operation
finish_embedding_index_operation = _part_15.finish_embedding_index_operation
index_embeddings_for_material = _part_15.index_embeddings_for_material
verify_embeddings = _part_15.verify_embeddings
rebuild_embeddings_for_material = _part_15.rebuild_embeddings_for_material
run_hybrid_retrieval = _part_16.run_hybrid_retrieval
run_vector_retrieval = _part_16.run_vector_retrieval
run_chunk_retrieval = _part_16.run_chunk_retrieval
get_material_index_status = _part_16.get_material_index_status
reclaim_stale_qa_operations = _part_16.reclaim_stale_qa_operations
get_idempotent_qa_response = _part_17.get_idempotent_qa_response
qa_request_fingerprint = _part_17.qa_request_fingerprint
create_qa_request = _part_17.create_qa_request
fail_qa_operation = _part_17.fail_qa_operation
persist_qa_answer = _part_17.persist_qa_answer
validate_citation_key = _part_17.validate_citation_key
assemble_context = _part_17.assemble_context

__all__ = ['RETRIEVAL_POLICY_VERSION', 'CONTEXT_ASSEMBLER_POLICY_VERSION', 'MAX_CONTEXT_TOKENS', 'CITATION_KEY_PREFIX', 'MAX_RETRIEVAL_QUERY_LENGTH', 'MAX_RETRIEVAL_TOP_K', 'VECTOR_POLICY_VERSION', 'HYBRID_POLICY_VERSION', 'FALLBACK_LEXICAL_POLICY_VERSION', 'RRF_K', 'VECTOR_CANDIDATE_POOL', 'MAX_QA_QUESTION_LENGTH', 'QA_PROMPT_VERSION', 'QA_OPERATION_LEASE_SECONDS', 'get_qa_citation_detail', 'list_qa_threads', 'get_qa_thread_history', 'create_or_get_revision', 'index_material_revision', 'reclaim_stale_embedding_operations', 'create_task_backed_embedding_operation', 'get_operation_task_public', 'create_embedding_index_operation', 'finish_embedding_index_operation', 'index_embeddings_for_material', 'verify_embeddings', 'rebuild_embeddings_for_material', 'run_hybrid_retrieval', 'run_vector_retrieval', 'run_chunk_retrieval', 'get_material_index_status', 'reclaim_stale_qa_operations', 'get_idempotent_qa_response', 'qa_request_fingerprint', 'create_qa_request', 'fail_qa_operation', 'persist_qa_answer', 'validate_citation_key', 'assemble_context']
