from __future__ import annotations

import hashlib

from .config import AppConfig
from .embedding import EmbeddingError
from .providers import EmbeddingProviderRegistry, ProviderError
from .repository import connect, index_embeddings_for_material
from .task_runner import TaskContext, TaskFailed, TaskResult, TaskRunner, TaskRunnerError

# Only this explicit, idempotent local indexing operation is approved in Phase 10-4.
# Generation, capture transcription, report aggregation and delivery remain synchronous.
EMBEDDING_TASK_KIND = "embedding_index"
EMBEDDING_RETRYABLE_ERRORS = frozenset({
    "embedding_provider_timeout", "embedding_provider_connection_failed",
    "embedding_provider_unavailable", "embedding_provider_rate_limited",
})


def _embedding_provider(config: AppConfig):
    provider_id = config.embedding_provider_id or "fake"
    return EmbeddingProviderRegistry(
        provider_id, config.embedding_model_id,
        model_revision=config.embedding_model_revision,
        base_url=config.embedding_base_url, api_key=config.embedding_api_key,
        timeout_seconds=config.embedding_timeout_seconds,
        max_batch_size=config.embedding_max_batch_size,
        max_text_chars=config.embedding_max_text_chars,
        max_dimensions=config.embedding_max_dimensions,
        max_response_bytes=config.embedding_max_response_bytes,
        max_retries=config.embedding_max_retries,
    ).configured_provider()


def embedding_provider_identity(config: AppConfig) -> tuple[str, str, str]:
    """Validate the runtime provider before accepting a task; no provider call occurs."""
    provider = _embedding_provider(config)
    return str(provider.provider_id), str(provider.model_id), str(provider.model_revision)


def _embedding_handler(config: AppConfig, context: TaskContext) -> TaskResult:
    context.progress(5, "indexing")
    try:
        provider = _embedding_provider(config)
    except (EmbeddingError, ProviderError) as error:
        raise TaskFailed(error.code) from None

    with connect(config.database_path) as connection:
        operation = connection.execute(
            "SELECT material_id,source_revision,input_fingerprint,provider_id,model_id "
            "FROM ai_operations WHERE id=? AND project_id=? AND operation_type='embedding_index' AND status='running'",
            (context.operation_id, context.project_id),
        ).fetchone()
        if operation is None or operation["material_id"] is None or operation["source_revision"] is None:
            raise TaskFailed("task_result_unavailable")
        if (str(operation["provider_id"]) != str(provider.provider_id) or
                str(operation["model_id"] or "") != str(provider.model_id)):
            raise TaskFailed("embedding_provider_changed")
        expected_fingerprint = hashlib.sha256(
            f"embedding_index\x1f{operation['material_id']}\x1f{operation['source_revision']}\x1f{provider.provider_id}\x1f{provider.model_id}\x1f{provider.model_revision}".encode("utf-8")
        ).hexdigest()
        if str(operation["input_fingerprint"]) != expected_fingerprint:
            raise TaskFailed("embedding_provider_changed")

        def checkpoint() -> bool:
            if context.cancel_requested():
                return False
            try:
                context.heartbeat()
            except TaskRunnerError as error:
                raise ValueError(error.code) from None
            return True

        try:
            result = index_embeddings_for_material(
                connection, material_id=str(operation["material_id"]), provider=provider,
                retry_failed=True, expected_revision_id=str(operation["source_revision"]),
                checkpoint=checkpoint,
            )
        except EmbeddingError as error:
            raise TaskFailed(error.code) from None
        except ProviderError as error:
            raise TaskFailed(error.code) from None
        except ValueError as error:
            code = str(error)
            if code == "task_cancel_requested":
                context.raise_if_cancel_requested()
            if code in {"source_stale", "source_deleted", "task_lease_lost"}: 
                raise TaskFailed(code) from None
            raise TaskFailed("embedding_index_failed") from None
    context.progress(95, "persisting")
    # A revision ID is an opaque persisted result handle, not source content.
    return TaskResult(output_artifact_id=str(operation["source_revision"]))


def build_task_runner(config: AppConfig, *, lease_seconds: int = 30) -> TaskRunner:
    """Build, but never start, the approved local runner registry."""
    runner = TaskRunner(config.database_path, lease_seconds=lease_seconds)
    runner.register(
        EMBEDDING_TASK_KIND, lambda context: _embedding_handler(config, context),
        retryable_error_codes=EMBEDDING_RETRYABLE_ERRORS,
    )
    return runner
