"""Runtime patches for KFP 2.5.0 metadata-writer bugs.

Mounted into metadata-writer pod and run as entrypoint.
Monkey-patches modules, then runs the original metadata_writer.py.

Patch 1: metadata_helpers.connect_to_mlmd() - gRPC max message size
  Original: https://github.com/kubeflow/pipelines/blob/2.5.0/backend/metadata_writer/src/metadata_helpers.py#L33-L57
  Upstream issue: https://github.com/kubeflow/pipelines/issues/11949
  Upstream fix (2.15.0): https://github.com/kubeflow/pipelines/pull/12438
  Changes: Read METADATA_GRPC_MAX_RECEIVE_MESSAGE_LENGTH env var and set on gRPC config.

Patch 2: os.remove - debug file cleanup FileNotFoundError
  Original: https://github.com/kubeflow/pipelines/blob/2.5.0/backend/metadata_writer/src/metadata_writer.py#L185
  Upstream issue: https://github.com/kubeflow/pipelines/issues/12468
  Upstream fix (not yet released): https://github.com/kubeflow/pipelines/pull/12469
  Root cause: debug_paths deque persists across K8s watch reconnections. When the watch
    times out and reconnects, all pods are re-listed as ADDED events. Pods with unchanged
    resource_versions produce duplicate file paths in the deque. First cleanup deletes the
    file; second cleanup hits FileNotFoundError and crashes the process.
  Changes: Wrap os.remove to silently ignore FileNotFoundError.

Patch 3: metadata_helpers.get_or_create_context_with_type() - AlreadyExistsError race condition
  Original: https://github.com/kubeflow/pipelines/blob/2.5.0/backend/metadata_writer/src/metadata_helpers.py#L170-L196
  Root cause: Multiple metadata-writer replicas race to create the same context. Both call
    get_context_by_name() (cache miss), then put_contexts(). The second put_contexts() fails
    with AlreadyExistsError (MySQL duplicate key on Context.type_id). The unhandled exception
    propagates up and crashes the process, causing CrashLoopBackOff.
  Changes: Catch AlreadyExistsError after put_contexts() fails and fall back to
    get_context_by_name(), clearing the LRU cache so the re-fetch hits the store.
"""

import os
import sys
from time import sleep

from ml_metadata.proto import metadata_store_pb2
from ml_metadata.metadata_store import metadata_store
from ml_metadata.errors import AlreadyExistsError


def connect_to_mlmd() -> metadata_store.MetadataStore:
    """Patched connect_to_mlmd - see module docstring for details."""
    import metadata_helpers  # original module, already in sys.modules

    print("=" * 60)
    print("connect_to_mlmd [PATCHED]")
    print("  Backport of kubeflow/pipelines#12438 for #11949")
    print("  Patch: {}".format(os.path.abspath(__file__)))
    print("  Python: {}".format(sys.version))
    print("  ml_metadata: {}".format(metadata_store.__file__))
    print("=" * 60)

    metadata_service_host = os.environ.get(
        'METADATA_GRPC_SERVICE_SERVICE_HOST', 'metadata-grpc-service')
    metadata_service_port = int(os.environ.get(
        'METADATA_GRPC_SERVICE_SERVICE_PORT', 8080))

    mlmd_connection_config = metadata_store_pb2.MetadataStoreClientConfig(
        host="[{}]".format(metadata_service_host) if metadata_helpers.isIPv6(metadata_service_host) else metadata_service_host,
        port=metadata_service_port,
    )

    max_receive_message_length = os.environ.get('METADATA_GRPC_MAX_RECEIVE_MESSAGE_LENGTH')
    if max_receive_message_length:
        try:
            max_length = int(max_receive_message_length)
            mlmd_connection_config.channel_arguments.max_receive_message_length = max_length
        except ValueError:
            print('WARNING: Invalid METADATA_GRPC_MAX_RECEIVE_MESSAGE_LENGTH="{}". Using default.'.format(
                max_receive_message_length), file=sys.stderr)

    print("--- gRPC Connection Config ---")
    print("  host: {}".format(metadata_service_host))
    print("  port: {}".format(metadata_service_port))
    print("  METADATA_GRPC_MAX_RECEIVE_MESSAGE_LENGTH: {}".format(
        max_receive_message_length if max_receive_message_length else "<not set, using default 4MB>"))
    print("  mlmd_connection_config: {}".format(mlmd_connection_config))
    print("------------------------------")
    sys.stdout.flush()

    for _ in range(100):
        try:
            mlmd_store = metadata_store.MetadataStore(mlmd_connection_config)
            _ = mlmd_store.get_context_types()
            return mlmd_store
        except Exception as e:
            print('Failed to access the Metadata store. Exception: "{}"'.format(str(e)), file=sys.stderr)
            sys.stderr.flush()
            sleep(1)

    raise RuntimeError('Could not connect to the Metadata store.')


def get_or_create_context_with_type(
    store,
    context_name,
    type_name,
    properties=None,
    type_properties=None,
    custom_properties=None,
):
    """Patched get_or_create_context_with_type - see module docstring Patch 3."""
    import metadata_helpers

    try:
        context = metadata_helpers.get_context_by_name(store, context_name)
    except:
        try:
            context = metadata_helpers.create_context_with_type(
                store=store,
                context_name=context_name,
                type_name=type_name,
                properties=properties,
                type_properties=type_properties,
                custom_properties=custom_properties,
            )
            return context
        except AlreadyExistsError:
            print('Context "{}" already exists (race condition), fetching existing.'.format(
                context_name), flush=True)
            metadata_helpers.get_context_by_name.cache_clear()
            context = metadata_helpers.get_context_by_name(store, context_name)

    # Verify the context has the expected type name
    context_types = store.get_context_types_by_id([context.type_id])
    assert len(context_types) == 1
    if context_types[0].name != type_name:
        raise RuntimeError(
            'Context "{}" was found, but it has type "{}" instead of "{}"'.format(
                context_name, context_types[0].name, type_name))
    return context


if __name__ == "__main__":
    import metadata_helpers
    metadata_helpers.connect_to_mlmd = connect_to_mlmd
    print("metadata_writer_patch: patched metadata_helpers.connect_to_mlmd", flush=True)

    # Patch os.remove to ignore FileNotFoundError (kubeflow/pipelines#12468).
    # debug_paths deque accumulates duplicate paths across watch reconnections;
    # second removal of the same path crashes the process.
    _original_os_remove = os.remove
    def _safe_remove(path, *args, **kwargs):
        try:
            _original_os_remove(path, *args, **kwargs)
        except FileNotFoundError:
            pass
    os.remove = _safe_remove
    print("metadata_writer_patch: patched os.remove to ignore FileNotFoundError", flush=True)

    metadata_helpers.get_or_create_context_with_type = get_or_create_context_with_type
    print("metadata_writer_patch: patched metadata_helpers.get_or_create_context_with_type", flush=True)

    import runpy
    runpy.run_path("/kfp/metadata_writer/metadata_writer.py", run_name="__main__")
