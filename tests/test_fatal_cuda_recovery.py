"""Fatal CUDA errors must fail the service, not leave a broken worker alive."""
from unittest.mock import patch

import pytest

from mysuperwhisper import main, transcription


@pytest.mark.parametrize("message", [
    "CUDA error: unspecified launch failure",
    "cudaErrorLaunchFailure",
    "CUDA error: device-side assert triggered",
    "CUDA error: an illegal memory access was encountered",
    "cudaErrorContextIsDestroyed",
])
def test_fatal_cuda_error(message):
    assert transcription.is_fatal_cuda_error(RuntimeError(message))


@pytest.mark.parametrize("message", [
    "CUDA out of memory", "CUBLAS_STATUS_ALLOC_FAILED", "download failed",
])
def test_recoverable_errors_do_not_exit(message):
    with patch.object(main.os, "_exit") as exit_process:
        main.exit_on_fatal_cuda_error(RuntimeError(message))
    exit_process.assert_not_called()


def test_model_load_failure_exits_before_cuda_cleanup():
    error = RuntimeError("CUDA error: unspecified launch failure")
    with patch.object(main, "_is_model_loaded", False), \
         patch.object(main, "_is_model_loading", False), \
         patch.object(main, "_model_load_error", None), \
         patch.object(transcription, "load_model", side_effect=error), \
         patch.object(transcription, "unload_model") as unload, \
         patch.object(main.os, "_exit", side_effect=SystemExit(1)) as exit_process:
        with pytest.raises(SystemExit) as result:
            main.lazy_load_model()
    assert result.value.code == 1
    exit_process.assert_called_once_with(1)
    unload.assert_not_called()
