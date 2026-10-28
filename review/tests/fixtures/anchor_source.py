"""Frozen anchor for the review/tests/test_validate.py fixtures. Do not edit.

The fixtures cite line 14 of this file and quote it. It used to be
runs/ai/marketing-comms/src/model/gateway.py, which is live code and drifted.
"""


class AnthropicAdapter:
    def __init__(self) -> None:
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client
