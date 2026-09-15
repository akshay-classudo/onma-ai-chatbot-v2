def anonymize_ip(ip: str) -> str | None:
    """Zero the last IPv4 octet / truncate IPv6 — never store a full raw IP."""
    if not ip:
        return None

    if "." in ip:
        parts = ip.split(".")
        if len(parts) == 4:
            parts[3] = "0"
            return ".".join(parts)

    if ":" in ip:
        parts = ip.split(":")
        return ":".join(parts[:4]) + "::"

    return None


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
