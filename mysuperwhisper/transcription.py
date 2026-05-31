"""
Granite speech transcription engine for MySuperWhisper.
Handles model loading and speech-to-text conversion.
"""

import gc
import importlib
import importlib.util
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
        return "cuda", _torch.bfloat16, False
    return "cpu", _torch.float32, True


def _build_prompt():
    return (
        "<|audio|>transcribe the speech with proper punctuation and capitalization. "
        "Output only the transcription as valid plain text. Preserve line breaks when "
        "the speaker clearly dictates separate lines."
    )


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
    model = _transformers.AutoModelForSpeechSeq2Seq.from_pretrained(
        model_name,
        torch_dtype=dtype,
    )
    model.to(device)
    model.eval()

    _main_processor = processor
    _main_tokenizer = processor.tokenizer
    _main_model = model
    _is_cpu_mode = cpu_mode

    if cpu_mode:
        log("Granite transcription model loaded on CPU (degraded mode).", "warning")
    else:
        log("Granite transcription model loaded on GPU.")


def _load_preview_model(model_name):
    global _preview_model, _preview_processor

    _preview_model = None
    _preview_processor = None

    if not _torch.cuda.is_available():
        log("Live preview model disabled because CUDA is unavailable.", "warning")
        return

    if importlib.util.find_spec("flash_attn") is None:
        log("Live preview model disabled because flash-attn is not installed.", "warning")
        return

    try:
        log(f"Loading Granite preview model '{model_name}' on cuda...")
        processor = _transformers.AutoProcessor.from_pretrained(
            model_name,
            trust_remote_code=True,
        )
        model = _transformers.AutoModel.from_pretrained(
            model_name,
            trust_remote_code=True,
            attn_implementation="flash_attention_2",
            torch_dtype=_torch.bfloat16,
        )
        model.to("cuda")
        model.eval()
        _preview_processor = processor
        _preview_model = model
        log("Granite preview model loaded on GPU.")
    except Exception as exc:
        _preview_model = None
        _preview_processor = None
        log(f"Preview model unavailable: {exc}", "warning")


def load_model(model_name=None):
    """
    Load the Granite speech models.

    Args:
        model_name: Optional main transcription model override.

    Returns:
        bool: True if GPU mode, False if CPU mode
    """
    _ensure_dependencies()

    selected_model = model_name or config.transcription_model
    _load_main_model(selected_model)
    _load_preview_model(config.preview_model)
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

    _ensure_dependencies()

    target_main_model = new_model_name or config.transcription_model
    target_preview_model = preview_model_name or config.preview_model
    log(
        f"Reloading Granite models: main='{target_main_model}', preview='{target_preview_model}'..."
    )

    try:
        unload_model()
        _load_main_model(target_main_model)
        _load_preview_model(target_preview_model)
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
    global _main_model, _main_processor, _main_tokenizer, _preview_model, _preview_processor, _is_cpu_mode

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

    if unloaded:
        gc.collect()
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
    with _torch.inference_mode():
        output = _preview_model.transcribe(**inputs)
    transcriptions = _preview_processor.batch_decode(output.preds)
    return transcriptions[0].strip() if transcriptions else ""


def transcribe(audio_data, language=None, task="transcribe", fast=False):
    """
    Transcribe audio to text.

    Args:
        audio_data: Audio data at 16kHz (use audio.prepare_for_transcription first)
        language: Language code ('fr', 'en', 'es', etc.)
                 If None, uses config.language
        fast: If True, uses the preview model when available
        task: Reserved for compatibility with the previous backend

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
        if fast and _preview_model is not None:
            return _transcribe_with_preview_model(audio_data)
        return _transcribe_with_main_model(audio_data)

    except Exception as exc:
        log(f"Transcription error: {exc}", "error")
        raise


def is_cpu_mode():
    """Check if model is running in CPU mode (degraded)."""
    return _is_cpu_mode


def is_model_loaded():
    """Check if model is loaded."""
    return _main_model is not None
