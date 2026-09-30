class MissingAPIKeyError(RuntimeError):
    """Raised when a judge/verdict backend needs ANTHROPIC_API_KEY and it's unset."""
