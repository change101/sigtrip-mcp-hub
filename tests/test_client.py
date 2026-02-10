import unittest

from src.client import parse_upstream_response


class ParseUpstreamResponseTests(unittest.TestCase):
    def test_extracts_structured_content_from_sse(self):
        payload = (
            'event: message\n'
            'data: {"jsonrpc":"2.0","result":{"structuredContent":{"prices":[{"roomType":"ASK"}]}}}\n\n'
            'data: [DONE]\n'
        )
        parsed = parse_upstream_response(payload, "text/event-stream")
        self.assertEqual(parsed, {"prices": [{"roomType": "ASK"}]})

    def test_falls_back_to_json_text_content(self):
        payload = "{\"jsonrpc\":\"2.0\",\"result\":{\"content\":[{\"type\":\"text\",\"text\":\"Result: {\\\"rooms\\\":[{\\\"roomDescription\\\":\\\"Standard\\\"}]}\"}]}}"
        parsed = parse_upstream_response(payload, "application/json")
        self.assertEqual(parsed, {"rooms": [{"roomDescription": "Standard"}]})

    def test_returns_text_fallback_when_json_not_found(self):
        payload = '{"jsonrpc":"2.0","result":{"content":[{"type":"text","text":"No JSON here"}]}}'
        parsed = parse_upstream_response(payload, "application/json")
        self.assertEqual(parsed, {"text_fallback": "No JSON here"})


if __name__ == "__main__":
    unittest.main()
