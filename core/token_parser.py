from urllib.parse import urlparse, parse_qs


def extract_token(url: str) -> str:
    """Extract JWT token from a WebWork download URL.

    Args:
        url: Full URL copied from the browser DevTools.

    Returns:
        The JWT token string.

    Raises:
        ValueError: If the URL is invalid or does not contain a token parameter.
    """
    if not url or not url.strip():
        raise ValueError(
            "URL inválida. Certifique-se de copiar a URL completa da "
            "requisição de exportação no DevTools."
        )

    url = url.strip()

    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    if "token" in params and params["token"][0]:
        return params["token"][0]

    # Fallback: try to find token= manually (handles edge cases)
    idx = url.find("token=")
    if idx == -1:
        raise ValueError(
            "URL inválida. Certifique-se de copiar a URL completa da "
            "requisição de exportação no DevTools."
        )

    token_start = idx + len("token=")
    remaining = url[token_start:]

    # Token ends at &data= or end of string
    amp_idx = remaining.find("&")
    if amp_idx == -1:
        token = remaining
    else:
        token = remaining[:amp_idx]

    if not token:
        raise ValueError(
            "URL inválida. Certifique-se de copiar a URL completa da "
            "requisição de exportação no DevTools."
        )

    return token
