"""
Granite speech transcription engine for MySuperWhisper.
Handles model loading and speech-to-text conversion.
"""

import gc
import importlib
import importlib.util
import threading
from typing import Any

from .config import log, config

# Global model instances
_main_model: Any = None
_main_processor: Any = None
_main_tokenizer: Any = None
_preview_model: Any = None
_preview_processor: Any = None
_torch: Any = None
_transformers: Any = None
_is_cpu_mode = False
_model_lock = threading.RLock()
_preview_load_thread = None
_preview_load_generation = None
_model_generation = 0


def _ensure_dependencies():
    global _torch, _transformers

    if _torch is not None and _transformers is not None:
        return

    try:
        torch = importlib.import_module("torch")
        transformers = importlib.import_module("transformers")
    except ImportError as exc:
        raise RuntimeError(
            "Granite speech dependencies are missing. Install torch, torchaudio, transformers, accelerate, and soundfile."
        ) from exc

    _torch = torch
    _transformers = transformers


def _get_device_and_dtype():
    if _torch.cuda.is_available():
        dtype = _torch.bfloat16 if _torch.cuda.is_bf16_supported() else _torch.float16
        return "cuda", dtype, False
    return "cpu", _torch.float32, True


def _build_prompt():
    return (
        "<|audio|>transcribe the speech with proper punctuation and capitalization. "
        "Output only the transcription as valid plain text. Preserve line breaks when "
        "the speaker clearly dictates separate lines. Use multiple paragraphs when "
        "the dictation naturally forms separate paragraphs or ideas."
    )


def _flush_cuda_cache():
    if _torch is None or not _torch.cuda.is_available():
        return

    _torch.cuda.empty_cache()
    try:
        _torch.cuda.ipc_collect()
    except RuntimeError as exc:
        log(f"CUDA IPC cleanup skipped: {exc}", "debug")


def _load_model_with_low_cpu_memory(model_class, model_name, device, **kwargs):
    """Load with reduced CPU peak memory, then move to the selected device."""
    model = None
    try:
        model = model_class.from_pretrained(
            model_name,
            low_cpu_mem_usage=True,
            **kwargs,
        )
        model.to(device)
        return model
    except Exception:
        if model is not None:
            del model
        gc.collect()
        _flush_cuda_cache()
        raise


def _estimate_max_new_tokens(audio_data, input_token_count):
    """Estimate a safe generation budget from the audio duration."""
    audio_seconds = max(len(audio_data) / 16000.0, 0.0)

    # Dictation usually stays well below this, but a generous budget helps avoid
    # truncating slower or more verbose speech.
    estimated_output_tokens = int(audio_seconds * 8) + 128

    generation_config = getattr(_main_model, "generation_config", None)
    model_max_length = getattr(generation_config, "max_length", None)
    if not model_max_length:
        model_max_length = getattr(_main_model.config, "max_position_embeddings", None)

    if model_max_length:
        available_tokens = max(int(model_max_length) - int(input_token_count), 128)
        if estimated_output_tokens > available_tokens:
            log(
                f"Estimated transcript may exceed model context; limiting generation to {available_tokens} tokens.",
                "warning",
            )
        return min(estimated_output_tokens, available_tokens)

    return estimated_output_tokens


def _load_main_model(model_name):
    global _main_model, _main_processor, _main_tokenizer, _is_cpu_mode

    device, dtype, cpu_mode = _get_device_and_dtype()
    log(f"Loading Granite transcription model '{model_name}' on {device}...")

    processor = _transformers.AutoProcessor.from_pretrained(model_name)
    model = _load_model_with_low_cpu_memory(
        _transformers.AutoModelForSpeechSeq2Seq,
        model_name,
        device,
        torch_dtype=dtype,
    )
    model.eval()

    _main_processor = processor
    _main_tokenizer = processor.tokenizer
    _main_model = model
    _is_cpu_mode = cpu_mode

    if cpu_mode:
        log("Granite transcription model loaded on CPU (degraded mode).", "warning")
    else:
        log("Granite transcription model loaded on GPU.")


def _load_preview_model(model_name, generation):
    global _preview_model, _preview_processor

    if not _torch.cuda.is_available():
        log("Live preview model disabled because CUDA is unavailable.", "warning")
        return

    try:
        log(f"Loading Granite preview model '{model_name}' on cuda...")
        processor = _transformers.AutoProcessor.from_pretrained(
            model_name,
            trust_remote_code=True,
        )
        model_kwargs = {
            "trust_remote_code": True,
            "torch_dtype": _get_device_and_dtype()[1],
        }
        if importlib.util.find_spec("flash_attn") is not None:
            model_kwargs["attn_implementation"] = "flash_attention_2"
        else:
            log("flash-attn is unavailable; loading Granite preview with standard attention.")
        model = _load_model_with_low_cpu_memory(
            _transformers.AutoModel,
            model_name,
            "cuda",
            **model_kwargs,
        )
        model.eval()
        if generation != _model_generation:
            del model
            gc.collect()
            _flush_cuda_cache()
            log("Discarded stale Granite preview model load.", "debug")
            return
        _preview_processor = processor
        _preview_model = model
        log("Granite preview model loaded on GPU.")
    except Exception as exc:
        if generation == _model_generation:
            _preview_model = None
            _preview_processor = None
        log(f"Preview model unavailable: {exc}", "warning")


def _start_preview_model_load(model_name):
    """Load the optional preview model without blocking final transcription."""
    global _preview_load_thread, _preview_load_generation

    if not config.live_preview_enabled:
        return
    if (
        _preview_load_thread
        and _preview_load_thread.is_alive()
        and _preview_load_generation == _model_generation
    ):
        return

    generation = _model_generation
    _preview_load_thread = threading.Thread(
        target=_load_preview_model,
        args=(model_name, generation),
        name="granite-preview-loader",
        daemon=True,
    )
    _preview_load_generation = generation
    _preview_load_thread.start()


def load_model(model_name=None):
    """
    Load the Granite speech models.

    Args:
        model_name: Optional main transcription model override.

    Returns:
        bool: True if GPU mode, False if CPU mode
    """
    with _model_lock:
        _ensure_dependencies()

        if _main_model is not None:
            return not _is_cpu_mode

        selected_model = model_name or config.transcription_model
        _load_main_model(selected_model)
        _start_preview_model_load(config.preview_model)
        return not _is_cpu_mode


def reload_model(new_model_name=None, preview_model_name=None):
    """
    Reload Granite speech models.

    Args:
        new_model_name: New main transcription model to load
        preview_model_name: New preview model to load

    Returns:
        bool: True if successful
    """
    global _main_model, _main_processor, _main_tokenizer, _preview_model, _preview_processor

    with _model_lock:
        _ensure_dependencies()

        target_main_model = new_model_name or config.transcription_model
        target_preview_model = preview_model_name or config.preview_model
        log(
            f"Reloading Granite models: main='{target_main_model}', preview='{target_preview_model}'..."
        )

        try:
            unload_model()
            _load_main_model(target_main_model)
            _start_preview_model_load(target_preview_model)
            config.transcription_model = target_main_model
            config.preview_model = target_preview_model
            return True

        except Exception as exc:
            log(f"Error reloading Granite models: {exc}", "error")
            _main_model = None
            _main_processor = None
            _main_tokenizer = None
            _preview_model = None
            _preview_processor = None
            return False


def unload_model():
    """Unload Granite speech models to free memory/VRAM."""
    global _main_model, _main_processor, _main_tokenizer, _preview_model, _preview_processor
    global _is_cpu_mode, _model_generation

    with _model_lock:
        _model_generation += 1
        unloaded = False

        if _main_model or _preview_model:
            log("Unloading model to free resources...")

        if _main_model:
            del _main_model
            _main_model = None
            unloaded = True

        if _preview_model:
            del _preview_model
            _preview_model = None
            unloaded = True

        _main_processor = None
        _main_tokenizer = None
        _preview_processor = None
        _is_cpu_mode = False

        gc.collect()
        _flush_cuda_cache()
        if unloaded:
            log("CUDA model cache released.")
        return unloaded


def _transcribe_with_main_model(audio_data):
    device, _, _ = _get_device_and_dtype()
    prompt = _build_prompt()
    chat = [{"role": "user", "content": prompt}]
    prompt_text = _main_tokenizer.apply_chat_template(
        chat,
        tokenize=False,
        add_generation_prompt=True,
    )
    model_inputs = _main_processor(
        prompt_text,
        audio_data,
        return_tensors="pt",
    ).to(device)
    max_new_tokens = _estimate_max_new_tokens(
        audio_data,
        model_inputs["input_ids"].shape[-1],
    )

    with _model_lock:
        with _torch.inference_mode():
            model_outputs = _main_model.generate(
                **model_inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                num_beams=1,
            )

    num_input_tokens = model_inputs["input_ids"].shape[-1]
    new_tokens = model_outputs[:, num_input_tokens:]
    output_text = _main_tokenizer.batch_decode(
        new_tokens,
        add_special_tokens=False,
        skip_special_tokens=True,
    )
    return output_text[0].strip() if output_text else ""


def _transcribe_with_preview_model(audio_data):
    inputs = _preview_processor([audio_data], device="cuda")
    with _model_lock:
        with _torch.inference_mode():
            output = _preview_model.transcribe(**inputs)
    transcriptions = _preview_processor.batch_decode(output.preds)
    return transcriptions[0].strip() if transcriptions else ""


def transcribe(audio_data, language=None, fast=False):
    """
    Transcribe audio to text.

    Args:
        audio_data: Audio data at 16kHz (use audio.prepare_for_transcription first)
        language: Language code ('fr', 'en', 'es', etc.)
                 If None, uses config.language
        fast: If True, uses the preview model when available

    Returns:
        str: Transcribed text, or empty string if nothing detected
    """
    if _main_model is None:
        log("Model not loaded!", "error")
        return ""

    lang = language or config.language
    if lang:
        log(f"Transcribing with configured voice-command language '{lang}'.", "debug")

    try:
        with _model_lock:
            if fast and _preview_model is not None:
                return _transcribe_with_preview_model(audio_data)
            return _transcribe_with_main_model(audio_data)

    except Exception as exc:
        log(f"Transcription error: {exc}", "error")
        raise


def is_out_of_vram_error(exc):
    """Return whether an exception represents a CUDA/GPU allocation failure."""
    if _torch is not None:
        cuda_module = getattr(_torch, "cuda", None)
        oom_type = getattr(cuda_module, "OutOfMemoryError", None)
        if oom_type is not None and isinstance(exc, oom_type):
            return True

    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "cuda out of memory",
            "cublas_status_alloc_failed",
            "cudnn_status_alloc_failed",
            "hip out of memory",
            "gpu out of memory",
        )
    )


def is_cpu_mode():
    """Check if model is running in CPU mode (degraded)."""
    return _is_cpu_mode


def is_model_loaded():
    """Check if model is loaded."""
    return _main_model is not None
