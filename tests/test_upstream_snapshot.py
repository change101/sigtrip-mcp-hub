import unittest

from scripts.upstream_diagnostics_snapshot import sanitize_mcp_name


class UpstreamSnapshotNamingTests(unittest.TestCase):
    def test_sanitize_https_url(self):
        self.assertEqual(sanitize_mcp_name("https://hotel.sigtrip.ai/mcp"), "hotel_sigtrip_ai-mcp")

    def test_sanitize_http_url(self):
        self.assertEqual(sanitize_mcp_name("http://example.com/a/b"), "example_com-a-b")


if __name__ == "__main__":
    unittest.main()
