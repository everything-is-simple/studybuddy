"""Local capability detection for out-of-box enablement.

Probes the host for optional local components (PaddleOCR models, RapidOCR
package models, whisper.cpp runtime and model) so that an installed capability
is enabled by default instead of requiring hand-copied environment variables.

Rules:
- Detection is read-only. It never downloads, installs, writes, or opens a
  network connection, and it never imports a heavy inference package.
- Explicit configuration always wins over detection.
- Absolute paths stay internal. The public projection exposes only stable
  status codes and non-sensitive identities.
"""
from __future__ import annotations

import importlib.util
import os
import string
from dataclasses import dataclass
from pathlib import Path

PADDLE_DET_DIR = "PP-OCRv5_server_det"
PADDLE_REC_DIR = "PP-OCRv5_server_rec"
_PADDLE_MODEL_FILES = ("inference.json", "inference.pdmodel", "inference.pdiparams")
_WHISPER_EXECUTABLE = "main.exe"
_WHISPER_MODEL_GLOB = "ggml-*.bin"

# Conventional install folder names probed under each existing drive root or
# home directory. Kept small and explicit; no recursive filesystem walk.
_PADDLE_ROOT_NAMES = ("PaddleOCR/models", "PaddleOCR/model", "paddleocr/models")
_WHISPER_ROOT_NAMES = ("WhisperCli", "Whisper/cli", "Whisper", "whisper.cpp")

STATUS_AVAILABLE = "available"
STATUS_NOT_INSTALLED = "not_installed"
STATUS_NOT_CONFIGURED = "not_configured"
STATUS_DISABLED = "disabled"


@dataclass(frozen=True)
class DetectedComponent:
    """One probed component. `path` stays internal and is never published."""

    status: str
    reason: str | None = None
    path: Path | None = None
    secondary_path: Path | None = None
    identity: str | None = None

    @property
    def available(self) -> bool:
        return self.status == STATUS_AVAILABLE


def _module_installed(name: str) -> bool:
    """Check import availability without executing the package."""
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _module_directory(name: str) -> Path | None:
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    for location in spec.submodule_search_locations:
        candidate = Path(location)
        if candidate.is_dir():
            return candidate
    return None


def _search_roots(preferred: Path | None = None) -> list[Path]:
    """Bounded set of base directories probed for conventional installs.

    When `preferred` is given (normally the configured `data_root`), its drive or
    mount anchor is probed first so a mirrored second drive cannot shadow the
    installation the user actually works from.
    """
    roots: list[Path] = []
    if preferred is not None:
        try:
            anchor = Path(preferred).resolve().anchor
        except (OSError, RuntimeError, ValueError):
            anchor = ""
        if anchor:
            candidate = Path(anchor)
            try:
                if candidate.is_dir():
                    roots.append(candidate)
            except OSError:
                pass
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:/")
            try:
                if drive.is_dir():
                    roots.append(drive)
            except OSError:
                continue
    else:
        roots.extend(path for path in (Path("/opt"), Path("/usr/local/share")) if path.is_dir())
    try:
        home = Path.home()
    except (OSError, RuntimeError):
        home = None
    if home is not None and home.is_dir():
        roots.append(home)
        roots.append(home / ".studybuddy")
    unique: list[Path] = []
    for root in roots:
        if root not in unique:
            unique.append(root)
    return unique


def _valid_paddle_model_root(root: Path) -> bool:
    try:
        if not root.is_dir():
            return False
        for name in (PADDLE_DET_DIR, PADDLE_REC_DIR):
            model_dir = root / name
            if not model_dir.is_dir():
                return False
            if not any((model_dir / file).is_file() for file in _PADDLE_MODEL_FILES):
                return False
    except OSError:
        return False
    return True


def detect_paddle_ocr(explicit_root: Path | str | None = None,
                      *, preferred_base: Path | None = None) -> DetectedComponent:
    """Locate a usable local PP-OCRv5 model root for PaddleOCR."""
    if not _module_installed("paddleocr") or not _module_installed("paddle"):
        return DetectedComponent(STATUS_NOT_INSTALLED, "paddleocr_package_missing")
    if explicit_root is not None:
        root = Path(explicit_root)
        if _valid_paddle_model_root(root):
            return DetectedComponent(STATUS_AVAILABLE, None, root,
                                     identity=f"{PADDLE_DET_DIR}+{PADDLE_REC_DIR}")
        return DetectedComponent(STATUS_NOT_CONFIGURED, "ocr_model_root_invalid")
    for base in _search_roots(preferred_base):
        for name in _PADDLE_ROOT_NAMES:
            candidate = base / name
            if _valid_paddle_model_root(candidate):
                return DetectedComponent(STATUS_AVAILABLE, None, candidate,
                                         identity=f"{PADDLE_DET_DIR}+{PADDLE_REC_DIR}")
    return DetectedComponent(STATUS_NOT_CONFIGURED, "ocr_model_root_not_found")


def detect_rapid_ocr() -> DetectedComponent:
    """Check the RapidOCR ONNX package and its bundled model files."""
    if not _module_installed("rapidocr_onnxruntime"):
        return DetectedComponent(STATUS_NOT_INSTALLED, "rapidocr_package_missing")
    if not _module_installed("onnxruntime"):
        return DetectedComponent(STATUS_NOT_INSTALLED, "onnxruntime_missing")
    package_dir = _module_directory("rapidocr_onnxruntime")
    if package_dir is None:
        return DetectedComponent(STATUS_NOT_CONFIGURED, "rapidocr_package_unreadable")
    models = package_dir / "models"
    try:
        has_models = models.is_dir() and any(models.glob("*.onnx"))
    except OSError:
        has_models = False
    if not has_models:
        return DetectedComponent(STATUS_NOT_CONFIGURED, "rapidocr_models_not_found")
    return DetectedComponent(STATUS_AVAILABLE, None, models,
                             identity="ch_PP-OCRv4_det_infer+ch_PP-OCRv4_rec_infer")


def _whisper_model_for(root: Path) -> Path | None:
    for base in (root / "Models", root / "models", root, root.parent / "Models",
                 root.parent / "models"):
        try:
            if not base.is_dir():
                continue
            for model in sorted(base.glob(_WHISPER_MODEL_GLOB)):
                if model.is_file():
                    return model
        except OSError:
            continue
    return None


def detect_whisper_asr(explicit_runtime: Path | str | None = None,
                       explicit_model: Path | str | None = None,
                       *, preferred_base: Path | None = None) -> DetectedComponent:
    """Locate a whisper.cpp-compatible executable together with a ggml model."""
    if explicit_runtime is not None:
        runtime = Path(explicit_runtime)
        if not runtime.is_file():
            return DetectedComponent(STATUS_NOT_CONFIGURED, "asr_runtime_invalid")
        model = Path(explicit_model) if explicit_model is not None else _whisper_model_for(runtime.parent)
        if model is None or not model.is_file():
            return DetectedComponent(STATUS_NOT_CONFIGURED, "asr_model_not_found")
        return DetectedComponent(STATUS_AVAILABLE, None, runtime, model, identity=model.stem)
    for base in _search_roots(preferred_base):
        for name in _WHISPER_ROOT_NAMES:
            runtime = base / name / _WHISPER_EXECUTABLE
            try:
                if not runtime.is_file():
                    continue
            except OSError:
                continue
            model = _whisper_model_for(runtime.parent)
            if model is not None:
                return DetectedComponent(STATUS_AVAILABLE, None, runtime, model, identity=model.stem)
    return DetectedComponent(STATUS_NOT_CONFIGURED, "asr_runtime_not_found")


@dataclass(frozen=True)
class DetectionResult:
    paddle_ocr: DetectedComponent
    rapid_ocr: DetectedComponent
    whisper_asr: DetectedComponent

    @property
    def ocr(self) -> DetectedComponent:
        """Primary OCR component; PaddleOCR is the approved primary path."""
        return self.paddle_ocr


def detect_all(*, ocr_model_root: Path | str | None = None,
               asr_runtime: Path | str | None = None,
               asr_model: Path | str | None = None,
               preferred_base: Path | None = None) -> DetectionResult:
    """Probe every optional local component once."""
    return DetectionResult(
        paddle_ocr=detect_paddle_ocr(ocr_model_root, preferred_base=preferred_base),
        rapid_ocr=detect_rapid_ocr(),
        whisper_asr=detect_whisper_asr(asr_runtime, asr_model, preferred_base=preferred_base),
    )


def public_component(component: DetectedComponent, *, enabled: bool = True) -> dict[str, object]:
    """Project one component for API/UI use without leaking filesystem paths."""
    status = component.status
    if status == STATUS_AVAILABLE and not enabled:
        status = STATUS_DISABLED
    return {
        "status": status,
        "installed": component.status != STATUS_NOT_INSTALLED,
        "detected": component.available,
        "reason": component.reason,
        "model_id": component.identity,
    }
