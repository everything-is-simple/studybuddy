"""本地能力检测 - 为开箱启用提供支持。

探测主机上的可选本地组件（PaddleOCR 模型、RapidOCR 包模型、
whisper.cpp 运行时和模型），使已安装的能力默认启用，而无需
手动复制环境变量。

规则：
- 检测是只读的，从不下载、安装、写入或打开网络连接
- 不导入重型推理包（仅检查模块可用性）
- 显式配置总是优先于检测结果
- 绝对路径不对外暴露，公共投影仅显示状态码和非敏感标识

检测策略：
- PaddleOCR: 探测各驱动器根目录下的常见安装路径
- RapidOCR: 检查 Python 包安装和内置模型
- Whisper.cpp: 探测可执行文件和对应 ggml 模型

状态值：
- available: 组件可用
- not_installed: 未安装（缺少包或文件）
- not_configured: 已安装但配置无效
- disabled: 已安装但被禁用

检测范围：
- Windows: 所有存在的驱动器 + 用户目录
- Linux: /opt, /usr/local/share, 用户目录
- 优先基准：如提供 preferred_base，其所在驱动器优先探测
- 不递归扫描文件系统，仅检查常见路径
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
    """一个探测结果组件。
    
    `path` 和 `secondary_path` 仅内部使用，从不对外发布。
    
    Attributes:
        status: 状态码（available/not_installed/not_configured/disabled）
        reason: 原因码（如 'paddleocr_package_missing'）
        path: 主路径（如模型根目录、可执行文件）
        secondary_path: 次要路径（如 Whisper 模型文件）
        identity: 组件标识（如模型名称）
    
    属性：
        available: True 表示组件可用
    """
    status: str
    reason: str | None = None
    path: Path | None = None
    secondary_path: Path | None = None
    identity: str | None = None

    @property
    def available(self) -> bool:
        """组件是否可用（status == 'available'）。"""
        return self.status == STATUS_AVAILABLE


def _module_installed(name: str) -> bool:
    """检查 Python 模块导入可用性（不执行包代码）。"""
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
    """定位可用的本地 PP-OCRv5 模型根目录。
    
    检查项：
    - paddleocr 和 paddle 包安装
    - 模型目录包含 PP-OCRv5_server_det 和 PP-OCRv5_server_rec
    - 每个模型目录包含 inference.pdmodel 等必需文件
    
    Args:
        explicit_root: 显式模型根目录（为 None 时自动探测）
        preferred_base: 优先基准目录（其所在驱动器优先探测）
    
    Returns:
        DetectedComponent 实例
    """
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
    """检查 RapidOCR ONNX 包和其内置模型文件。
    
    检查项：
    - rapidocr_onnxruntime 包安装
    - onnxruntime 包安装
    - 包内 models/ 目录包含 .onnx 文件
    
    Returns:
        DetectedComponent 实例
    """
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
    """定位 whisper.cpp 兼容可执行文件和 ggml 模型。
    
    检查项：
    - main.exe 可执行文件
    - ggml-*.bin 模型文件（在同目录或 Models/ 子目录）
    
    Args:
        explicit_runtime: 显式运行时路径（为 None 时自动探测）
        explicit_model: 显式模型路径
        preferred_base: 优先基准目录
    
    Returns:
        DetectedComponent 实例
    """
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
    """所有本地组件的检测结果。
    
    Attributes:
        paddle_ocr: PaddleOCR 组件
        rapid_ocr: RapidOCR 组件
        whisper_asr: Whisper.cpp 组件
    
    属性：
        ocr: 主 OCR 组件（PaddleOCR 为主要路径）
    """
    paddle_ocr: DetectedComponent
    rapid_ocr: DetectedComponent
    whisper_asr: DetectedComponent

    @property
    def ocr(self) -> DetectedComponent:
        """主 OCR 组件 - PaddleOCR 为批准的主要路径。"""
        return self.paddle_ocr


def detect_all(*, ocr_model_root: Path | str | None = None,
               asr_runtime: Path | str | None = None,
               asr_model: Path | str | None = None,
               preferred_base: Path | None = None) -> DetectionResult:
    """探测所有可选本地组件（执行一次）。
    
    Args:
        ocr_model_root: 显式 OCR 模型根目录
        asr_runtime: 显式 ASR 运行时路径
        asr_model: 显式 ASR 模型路径
        preferred_base: 优先基准目录（如 data_root）
    
    Returns:
        DetectionResult 包含所有组件的检测结果
    """
    return DetectionResult(
        paddle_ocr=detect_paddle_ocr(ocr_model_root, preferred_base=preferred_base),
        rapid_ocr=detect_rapid_ocr(),
        whisper_asr=detect_whisper_asr(asr_runtime, asr_model, preferred_base=preferred_base),
    )


def public_component(component: DetectedComponent, *, enabled: bool = True) -> dict[str, object]:
    """将组件投影为 API/UI 使用的格式（不泄露文件系统路径）。
    
    Args:
        component: 检测结果组件
        enabled: 是否启用（False 时 available 转为 disabled）
    
    Returns:
        公共投影字典，包含 status, installed, detected, reason, model_id
    """
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
