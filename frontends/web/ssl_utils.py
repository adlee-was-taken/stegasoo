"""
SSL Certificate Utilities

Auto-generates self-signed certificates for HTTPS.
Uses cryptography library (already a dependency).
"""

import datetime
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _get_local_ips() -> list[str]:
    """Get local IP addresses for this machine."""
    ips = []
    try:
        # Get hostname and resolve to IP
        hostname = socket.gethostname()
        for addr_info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = addr_info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass

    # Also try connecting to external to get primary interface IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        if ip not in ips:
            ips.append(ip)
        s.close()
    except Exception:
        pass

    return ips


def get_cert_paths(base_dir: Path) -> tuple[Path, Path]:
    """Get paths for cert and key files."""
    cert_dir = base_dir / "certs"
    cert_dir.mkdir(parents=True, exist_ok=True)
    return cert_dir / "server.crt", cert_dir / "server.key"


def certs_exist(base_dir: Path) -> bool:
    """Check if both cert files exist."""
    cert_path, key_path = get_cert_paths(base_dir)
    return cert_path.exists() and key_path.exists()


def generate_self_signed_cert(
    base_dir: Path,
    hostname: str = "localhost",
    days_valid: int = 365,
) -> tuple[Path, Path]:
    """
    Generate self-signed SSL certificate.

    Args:
        base_dir: Base directory for certs folder
        hostname: Server hostname for certificate
        days_valid: Certificate validity in days

    Returns:
        Tuple of (cert_path, key_path)
    """
    cert_path, key_path = get_cert_paths(base_dir)

    # Generate RSA key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Stegasoo"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])

    # Subject Alternative Names
    san_list = [
        x509.DNSName(hostname),
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]

    # Add hostname.local for mDNS access
    if not hostname.endswith(".local"):
        san_list.append(x509.DNSName(f"{hostname}.local"))

    # Add the hostname as IP if it looks like one
    try:
        san_list.append(x509.IPAddress(ipaddress.IPv4Address(hostname)))
    except ipaddress.AddressValueError:
        pass

    # Add local network IPs
    for local_ip in _get_local_ips():
        try:
            ip_addr = ipaddress.IPv4Address(local_ip)
            if x509.IPAddress(ip_addr) not in san_list:
                san_list.append(x509.IPAddress(ip_addr))
        except (ipaddress.AddressValueError, ValueError):
            pass

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=days_valid))
        .add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    # Write key file (chmod 600)
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)

    # Write cert file
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    return cert_path, key_path


def ensure_certs(base_dir: Path, hostname: str = "localhost") -> tuple[Path, Path]:
    """Ensure certificates exist, generating if needed."""
    if certs_exist(base_dir):
        return get_cert_paths(base_dir)

    print(f"Generating self-signed SSL certificate for {hostname}...")
    return generate_self_signed_cert(base_dir, hostname)
