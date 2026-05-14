import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}


def is_safe_url(url: str) -> bool:
    """
    True tylko gdy URL jest publiczny i ma dozwolony schemat.
    Odrzuca: file/ftp/gopher, RFC1918, 127.0.0.0/8, 169.254.0.0/16
    (metadata cloud), 0.0.0.0, multicast, reserved — także w IPv6.
    """
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False

    host = parsed.hostname
    if not host:
        return False

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True
