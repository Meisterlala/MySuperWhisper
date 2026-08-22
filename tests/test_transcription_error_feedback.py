"""Regression tests for visible transcription failure feedback."""

from unittest.mock import Mock, patch

import pytest

import mysuperwhisper.main as main


def _run_one_work_item(*, model_loaded, model_error=None, transcribe_error=None):
    item = {"audio_data": object(), "prefetched": None}
    queue = Mock()
    queue.get.side_effect = [item, KeyboardInterrupt]

    with patch.object(main, "processing_queue", queue), \
         patch.object(main, "_is_model_loaded", model_loaded), \
         patch.object(main, "_is_model_loading", False), \
         patch.object(main, "_model_load_error", model_error), \
         patch.object(main.audio, "prepare_for_transcription", return_value=object()), \
         patch.object(main, "_transcribe_final_audio", side_effect=transcribe_error), \
         patch.object(main, "unload_model_on_demand") as unload_model, \
         patch.object(main, "play_sound") as play_sound, \
         patch.object(main, "send_notification") as send_notification, \
         patch.object(main.tray, "update_tray") as update_tray:
        with pytest.raises(KeyboardInterrupt):
            main.audio_processing_loop()

    return play_sound, send_notification, update_tray, unload_model


def test_transcription_exception_leaves_tray_in_error_state():
    play_sound, send_notification, update_tray, unload_model = _run_one_work_item(
        model_loaded=True,
        transcribe_error=RuntimeError("CUDA out of memory"),
    )

    play_sound.assert_called_with("error")
    send_notification.assert_called_with(
        "MySuperWhisper",
        "Out of GPU memory — close another GPU application and try again.",
        "dialog-error",
    )
    update_tray.assert_called_once_with(
        "error", error_message="Out of VRAM — close another GPU app"
    )
    unload_model.assert_called_once_with()


def test_model_load_failure_leaves_tray_in_error_state():
    play_sound, send_notification, update_tray, unload_model = _run_one_work_item(
        model_loaded=False,
        model_error=RuntimeError("CUDA out of memory"),
    )

    play_sound.assert_called_with("error")
    send_notification.assert_called_with(
        "MySuperWhisper",
        "Out of GPU memory — close another GPU application and try again.",
        "dialog-error",
    )
    update_tray.assert_called_once_with(
        "error", error_message="Out of VRAM — close another GPU app"
    )
    unload_model.assert_not_called()


def test_cublas_allocation_failure_is_detected_as_out_of_vram():
    assert main.transcription.is_out_of_vram_error(
        RuntimeError("CUDA error: CUBLAS_STATUS_ALLOC_FAILED when calling cublasCreate(handle)")
    )
