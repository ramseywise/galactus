"""The provider boundary.

`gateway.LLM` is the only interface the pipeline knows about. `AnthropicAdapter`
is one implementation; the fake adapter used in tests is another. Nothing
outside this package imports `anthropic`.
"""
