"""Runtime patch: let AngelBrush images be sent while a sandbox is selected.

AstrBot only delivers a local file through ``send_message_to_user`` when the
path is inside the session workspace or the temp directory. With
``provider_settings.computer_use_runtime = "sandbox"`` the "local runtime"
fallback is disabled, so every other local path is looked up inside the
sandbox and fails with ``FileNotFoundError``.

AngelBrush writes its output to
``data/plugin_data/astrbot_plugin_angel_brush/generated-images`` and hands
that absolute path to the model. This plugin widens exactly one decision --
``_can_send_local_file`` in ``astrbot.core.tools.message_tools`` -- by one
directory. No AstrBot source file is modified, so upstream upgrades stay
clean, and a renamed internal function only disables the patch with a loud
warning instead of breaking the bot.
"""

from pathlib import Path

from astrbot.api import logger
from astrbot.api.star import Star
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

LOG_TAG = "angel_brush_sendbox_fix"
BRUSH_PLUGIN_NAME = "astrbot_plugin_angel_brush"
BRUSH_IMAGES_DIR = (
    Path(get_astrbot_data_path())
    / "plugin_data"
    / BRUSH_PLUGIN_NAME
    / "generated-images"
).resolve(strict=False)

_PATCH_FLAG = "_angel_brush_sendbox_fix"


def _install_patch() -> bool:
    """Wrap AstrBot's local-file send check with one extra allowlist entry.

    Returns:
        True when the wrapper is installed or was already installed, False
        when AstrBot's internal function is missing.
    """
    try:
        import astrbot.core.tools.message_tools as message_tools
    except ImportError as exc:
        logger.warning("[%s] cannot import message_tools: %s", LOG_TAG, exc)
        return False

    original = getattr(message_tools, "_can_send_local_file", None)
    if original is None:
        logger.warning(
            "[%s] message_tools._can_send_local_file not found; patch not "
            "applied. Sending AngelBrush images with a sandbox selected will "
            "keep failing.",
            LOG_TAG,
        )
        return False

    if getattr(original, _PATCH_FLAG, False):
        logger.info("[%s] patch already installed", LOG_TAG)
        return True

    def _can_send_local_file(context, local_path, *args, **kwargs):
        """Allow Brush output, otherwise defer to AstrBot's own check."""
        try:
            target = Path(local_path).resolve(strict=False)
            if target.is_relative_to(BRUSH_IMAGES_DIR):
                return True
        except (OSError, RuntimeError, TypeError, ValueError):
            pass
        return original(context, local_path, *args, **kwargs)

    setattr(_can_send_local_file, _PATCH_FLAG, True)
    message_tools._can_send_local_file = _can_send_local_file
    logger.info(
        "[%s] local send allowlist extended: %s (exists=%s)",
        LOG_TAG,
        BRUSH_IMAGES_DIR,
        BRUSH_IMAGES_DIR.is_dir(),
    )
    return True


PATCH_APPLIED = _install_patch()


class AngelBrushSendboxFix(Star):
    """Expose AngelBrush output to the send path when a sandbox is selected."""
