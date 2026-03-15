from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "AgentActionConfirmationRead": "app.modules.plugin.schemas",
    "AgentActionPluginInvokeRequest": "app.modules.plugin.schemas",
    "AgentActionPluginInvokeResult": "app.modules.plugin.schemas",
    "AgentPluginInvokeRequest": "app.modules.plugin.schemas",
    "AgentPluginInvokeResult": "app.modules.plugin.schemas",
    "PluginExecutionRequest": "app.modules.plugin.schemas",
    "PluginExecutionResult": "app.modules.plugin.schemas",
    "PluginJobAttemptRead": "app.modules.plugin.schemas",
    "PluginJobCreate": "app.modules.plugin.schemas",
    "PluginJobDetailRead": "app.modules.plugin.schemas",
    "PluginJobEnqueueRequest": "app.modules.plugin.schemas",
    "PluginJobListItemRead": "app.modules.plugin.schemas",
    "PluginJobListRead": "app.modules.plugin.schemas",
    "PluginJobNotificationRead": "app.modules.plugin.schemas",
    "PluginJobNotificationSummaryRead": "app.modules.plugin.schemas",
    "PluginJobRead": "app.modules.plugin.schemas",
    "PluginJobResponseCreate": "app.modules.plugin.schemas",
    "PluginJobResponseRead": "app.modules.plugin.schemas",
    "PluginLocaleListRead": "app.modules.plugin.schemas",
    "PluginLocaleRead": "app.modules.plugin.schemas",
    "PluginManifest": "app.modules.plugin.schemas",
    "PluginManifestCapabilities": "app.modules.plugin.schemas",
    "PluginManifestChannelSpec": "app.modules.plugin.schemas",
    "PluginManifestContextReads": "app.modules.plugin.schemas",
    "PluginManifestEntrypoints": "app.modules.plugin.schemas",
    "PluginManifestLocaleSpec": "app.modules.plugin.schemas",
    "PluginManifestType": "app.modules.plugin.schemas",
    "PluginManifestRegionProviderSpec": "app.modules.plugin.schemas",
    "PluginMountCreate": "app.modules.plugin.schemas",
    "PluginMountRead": "app.modules.plugin.schemas",
    "PluginMountUpdate": "app.modules.plugin.schemas",
    "PluginRawRecordCreate": "app.modules.plugin.schemas",
    "PluginRawRecordRead": "app.modules.plugin.schemas",
    "PluginRunRead": "app.modules.plugin.schemas",
    "PluginRegistryItem": "app.modules.plugin.schemas",
    "PluginRegistrySnapshot": "app.modules.plugin.schemas",
    "PluginStateOverrideRead": "app.modules.plugin.schemas",
    "PluginStateUpdateRequest": "app.modules.plugin.schemas",
    "PluginSyncPipelineResult": "app.modules.plugin.schemas",
    "PluginJobError": "app.modules.plugin.job_service",
    "PluginJobNotFoundError": "app.modules.plugin.job_service",
    "PluginJobStateError": "app.modules.plugin.job_service",
    "cancel_plugin_job": "app.modules.plugin.job_service",
    "create_plugin_job": "app.modules.plugin.job_service",
    "create_plugin_job_notification": "app.modules.plugin.job_service",
    "get_plugin_job_detail": "app.modules.plugin.job_service",
    "list_allowed_plugin_job_actions": "app.modules.plugin.job_service",
    "list_plugin_jobs_page": "app.modules.plugin.job_service",
    "mark_plugin_job_attempt_failed": "app.modules.plugin.job_service",
    "mark_plugin_job_attempt_succeeded": "app.modules.plugin.job_service",
    "mark_plugin_job_attempt_timed_out": "app.modules.plugin.job_service",
    "record_plugin_job_response": "app.modules.plugin.job_service",
    "requeue_plugin_job": "app.modules.plugin.job_service",
    "start_plugin_job_attempt": "app.modules.plugin.job_service",
    "publish_plugin_job_updates": "app.modules.plugin.job_notifier",
    "PluginJobWorker": "app.modules.plugin.job_worker",
    "claim_next_plugin_job": "app.modules.plugin.job_worker",
    "enqueue_plugin_execution_job": "app.modules.plugin.job_worker",
    "execute_plugin_job": "app.modules.plugin.job_worker",
    "recover_plugin_jobs": "app.modules.plugin.job_worker",
    "run_plugin_job_worker_cycle": "app.modules.plugin.job_worker",
    "aconfirm_agent_action_plugin": "app.modules.plugin.agent_bridge",
    "ainvoke_agent_action_plugin": "app.modules.plugin.agent_bridge",
    "ainvoke_agent_plugin": "app.modules.plugin.agent_bridge",
    "confirm_agent_action_plugin": "app.modules.plugin.agent_bridge",
    "invoke_agent_action_plugin": "app.modules.plugin.agent_bridge",
    "invoke_agent_plugin": "app.modules.plugin.agent_bridge",
    "PluginExecutionError": "app.modules.plugin.service",
    "PluginManifestValidationError": "app.modules.plugin.service",
    "PluginServiceError": "app.modules.plugin.service",
    "disable_plugin": "app.modules.plugin.service",
    "delete_plugin_mount": "app.modules.plugin.service",
    "discover_plugin_manifests": "app.modules.plugin.service",
    "enqueue_household_plugin_job": "app.modules.plugin.service",
    "enable_plugin": "app.modules.plugin.service",
    "execute_plugin": "app.modules.plugin.service",
    "execute_household_plugin": "app.modules.plugin.service",
    "get_household_plugin": "app.modules.plugin.service",
    "ingest_plugin_raw_records_to_memory": "app.modules.plugin.service",
    "load_plugin_manifest": "app.modules.plugin.service",
    "list_plugin_mounts": "app.modules.plugin.service",
    "list_saved_plugin_raw_records": "app.modules.plugin.service",
    "list_registered_plugins": "app.modules.plugin.service",
    "list_registered_plugins_for_household": "app.modules.plugin.service",
    "list_registered_plugin_locales_for_household": "app.modules.plugin.service",
    "require_available_household_plugin": "app.modules.plugin.service",
    "register_plugin_mount": "app.modules.plugin.service",
    "resolve_plugin_household_region_context": "app.modules.plugin.service",
    "run_plugin_sync_pipeline": "app.modules.plugin.service",
    "save_plugin_raw_records": "app.modules.plugin.service",
    "set_household_plugin_enabled": "app.modules.plugin.service",
    "update_plugin_mount": "app.modules.plugin.service",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
