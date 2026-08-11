"""The provider boundary.

`port.LLM` is the only interface the pipeline knows about. The Anthropic adapter
is one implementation; the fake adapter used in tests is another. Nothing above
this package imports `anthropic`.
"""
