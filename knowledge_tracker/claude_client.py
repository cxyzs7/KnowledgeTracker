import logging
import time
import anthropic

logger = logging.getLogger(__name__)
BACKOFF = [1, 2, 4]


def call_with_retry(
    client: anthropic.Anthropic,
    *,
    model: str,
    max_tokens: int,
    tools: list[dict],
    messages: list[dict],
    tool_choice: dict | None = None,
    system: str | None = None,
) -> anthropic.types.Message:
    """Call Claude API with exponential backoff on 429/500 errors."""
    last_exc: Exception | None = None
    kwargs = dict(model=model, max_tokens=max_tokens, tools=tools, messages=messages)
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    if system:
        kwargs["system"] = system

    for i, backoff in enumerate([0] + BACKOFF):
        if backoff:
            time.sleep(backoff)
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            retry_after = _parse_retry_after(e)
            wait = retry_after if retry_after else BACKOFF[min(i, len(BACKOFF) - 1)]
            logger.warning("Rate limit hit, retrying in %ss (attempt %d/4)", wait, i + 1)
            time.sleep(wait)
            last_exc = e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                logger.warning("API error %s, retrying (attempt %d/4)", e.status_code, i + 1)
                last_exc = e
            else:
                raise
        except Exception as e:
            raise

    raise RuntimeError(f"Claude API call failed after 4 attempts") from last_exc


def _parse_retry_after(exc: anthropic.RateLimitError) -> int | None:
    """Extract Retry-After seconds from response headers, if present."""
    try:
        headers = exc.response.headers
        val = headers.get("retry-after") or headers.get("Retry-After")
        return int(val) if val else None
    except Exception:
        return None
