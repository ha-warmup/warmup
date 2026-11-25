"""Run pytest-homeassistant-custom-component against a newer Home Assistant.

The integration needs Home Assistant 2026.11, but the newest
pytest-homeassistant-custom-component release still pins 2026.10. CI
installs it with Home Assistant 2026.11 instead (see requirements_test.txt),
which needs two adjustments before that plugin is imported, so this module
is loaded first with ``-p tests.ha_compat``:

- Home Assistant must be imported before anything imports httpx, so that its
  httpx2 alias can be installed.
- pytest-homeassistant-custom-component imports ``_clear_logger_overwrites``
  from ``homeassistant.components.logger``; Home Assistant 2026.11 moved it to
  ``homeassistant.components.logger.helpers``.

Remove this module once pytest-homeassistant-custom-component supports the
Home Assistant version in requirements_test.txt.
"""

import homeassistant  # noqa: F401
import homeassistant.components.logger as ha_logger

if not hasattr(ha_logger, "_clear_logger_overwrites"):
    from homeassistant.components.logger.helpers import _clear_logger_overwrites

    ha_logger._clear_logger_overwrites = _clear_logger_overwrites
