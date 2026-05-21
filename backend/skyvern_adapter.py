"""CloakBrowser browser type registration for Skyvern BrowserContextFactory.

Registers 'cloakbrowser-cdp' and 'cloakbrowser-direct' browser types
that integrate CloakBrowser's stealth Chromium with Skyvern's workflow engine.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("cloakbrowser.manager.skyvern_adapter")

CLOAKBROWSER_MANAGER_URL = os.environ.get(
    "CLOAKBROWSER_MANAGER_URL", "http://127.0.0.1:8080"
)


def register_cloakbrowser_types() -> None:
    """Register CloakBrowser browser types into Skyvern's BrowserContextFactory.

    This should be called during application startup, after Skyvern's
    default types (chromium-headless, chromium-headful, cdp-connect)
    have been registered.
    """
    try:
        from skyvern.webeye.browser_factory import (
            BrowserArtifacts,
            BrowserCleanupFunc,
            BrowserContextFactory,
        )
        from playwright.async_api import BrowserContext, Playwright
    except ImportError:
        logger.warning(
            "Skyvern not installed, skipping CloakBrowser browser type registration"
        )
        return

    async def _create_cloakbrowser_cdp(
        playwright: Playwright,
        proxy_location: Any = None,
        extra_http_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> tuple[BrowserContext, BrowserArtifacts, BrowserCleanupFunc]:
        """Connect to a CloakBrowser instance via CDP through Manager.

        Uses the Manager's browser pool: sends a launch request to ensure
        the profile's browser is running, then connects via CDP.
        """
        profile_id = kwargs.get("browser_profile_id")

        if not profile_id:
            raise ValueError(
                "cloakbrowser-cdp requires browser_profile_id parameter"
            )

        manager_url = CLOAKBROWSER_MANAGER_URL
        cdp_url = f"{manager_url}/api/profiles/{profile_id}/cdp"

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{manager_url}/api/profiles/{profile_id}/launch",
                    timeout=60.0,
                )
                resp.raise_for_status()
                logger.info("Launched profile %s via Manager", profile_id)
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 409:
                    raise
                logger.info("Profile %s already running", profile_id)

        from skyvern.webeye.browser_factory import _connect_to_cdp_browser

        browser_context, browser_artifacts, cleanup = await _connect_to_cdp_browser(
            playwright,
            remote_browser_url=cdp_url,
            extra_http_headers=extra_http_headers,
            apply_download_behaviour=True,
        )

        return browser_context, browser_artifacts, cleanup

    async def _create_cloakbrowser_direct(
        playwright: Playwright,
        proxy_location: Any = None,
        extra_http_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> tuple[BrowserContext, BrowserArtifacts, BrowserCleanupFunc]:
        """Launch a CloakBrowser instance directly using the SDK.

        Bypasses the Manager's browser pool — useful for standalone
        Skyvern deployments without Manager.
        """
        from cloakbrowser import launch_persistent_context_async
        from skyvern.webeye.browser_factory import BrowserContextFactory

        import tempfile
        user_data_dir = tempfile.mkdtemp(prefix="cloakbrowser_")

        browser_args = BrowserContextFactory.build_browser_args(
            proxy_location=proxy_location,
            extra_http_headers=extra_http_headers,
        )

        context = await launch_persistent_context_async(
            user_data_dir=user_data_dir,
            headless=True,
            args=browser_args.get("args", []),
            viewport=browser_args.get("viewport", {"width": 1920, "height": 1080}),
            color_scheme=browser_args.get("color_scheme", "no-preference"),
            humanize=True,
            human_preset="default",
        )

        browser_artifacts = BrowserContextFactory.build_browser_artifacts(
            har_path=browser_args.get("record_har_path"),
            browser_session_dir=user_data_dir,
        )

        async def cleanup():
            await context.close()

        return context, browser_artifacts, cleanup

    BrowserContextFactory.register_type("cloakbrowser-cdp", _create_cloakbrowser_cdp)
    BrowserContextFactory.register_type("cloakbrowser-direct", _create_cloakbrowser_direct)

    logger.info(
        "Registered CloakBrowser browser types: cloakbrowser-cdp, cloakbrowser-direct"
    )
