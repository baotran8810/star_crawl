"""star_crawl — universal web crawler with content extraction."""

from __future__ import annotations

__version__ = "0.1.0"


def _enable_system_truststore() -> None:
    """Use the OS keychain for SSL verification.

    macOS shipped Pythons frequently fail with `CERTIFICATE_VERIFY_FAILED`
    when hitting modern sites (Medium custom domains, Cloudflare-fronted
    blogs, …) because the bundled `certifi` cacert is older than the leaf
    intermediates the sites serve. Injecting truststore makes httpx
    delegate to the OS, which is updated by the OS vendor.
    """
    try:
        import truststore  # noqa: PLC0415

        truststore.inject_into_ssl()
    except ImportError:
        # truststore is an optional but recommended dep; silently fall back
        # to certifi if not installed.
        pass


_enable_system_truststore()
