"""Runtime patch: metadata_helpers.connect_to_mlmd() - gRPC max message size

Original function (KFP 2.5.0):
  https://github.com/kubeflow/pipelines/blob/2.5.0/backend/metadata_writer/src/metadata_helpers.py#L33-L57

Upstream issue (not fixed in 2.5.0):
  https://github.com/kubeflow/pipelines/issues/8408

Changes from original:
  1. Read METADATA_GRPC_MAX_RECEIVE_MESSAGE_LENGTH env var (backport from KFP master)
  2. Set channel_arguments.max_receive_message_length on gRPC config
  3. Add startup diagnostic logging

Usage: Mounted into metadata-writer pod and run as entrypoint.
  Monkey-patches metadata_helpers.connect_to_mlmd, then runs the original metadata_writer.py.
"""

import os
import sys
from time import sleep

from ml_metadata.proto import metadata_store_pb2
from ml_metadata.metadata_store import metadata_store


def connect_to_mlmd() -> metadata_store.MetadataStore:
    """Patched connect_to_mlmd - see module docstring for details."""
    import metadata_helpers  # original module, already in sys.modules

    print("=" * 60)
    print("connect_to_mlmd [PATCHED] - deployKF gRPC fix")
    print("  Backport of kubeflow/pipelines master fix for #8408")
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


if __name__ == "__main__":
    # Apply monkey-patch and run the original entrypoint
    import metadata_helpers
    metadata_helpers.connect_to_mlmd = connect_to_mlmd
    print("grpc_patch: patched metadata_helpers.connect_to_mlmd", flush=True)

    import runpy
    runpy.run_path("/kfp/metadata_writer/metadata_writer.py", run_name="__main__")
