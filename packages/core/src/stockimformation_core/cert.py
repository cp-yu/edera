from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


@dataclass(frozen=True)
class IssuedCertificate:
    cert_path: Path
    key_path: Path
    common_name: str


class CertificateAuthority:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.ca_key_path = data_dir / "ca.key"
        self.ca_cert_path = data_dir / "ca.crt"

    def ensure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.ca_key_path.exists() and self.ca_cert_path.exists():
            return
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cert = (
            x509.CertificateBuilder()
            .subject_name(_name("rig-ca"))
            .issuer_name(_name("rig-ca"))
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256())
        )
        self.ca_key_path.write_bytes(_private_key_bytes(key))
        self.ca_cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    def issue_client(self, common_name: str, ttl_seconds: int = 3600) -> IssuedCertificate:
        return self._issue(common_name, ttl_seconds, "client")

    def issue_server(self, common_name: str = "localhost", ttl_seconds: int = 365 * 24 * 3600) -> IssuedCertificate:
        return self._issue(common_name, ttl_seconds, "server")

    def ca_cert_pem(self) -> bytes:
        self.ensure()
        return self.ca_cert_path.read_bytes()

    def _issue(self, common_name: str, ttl_seconds: int, name: str) -> IssuedCertificate:
        self.ensure()
        ca_key = serialization.load_pem_private_key(self.ca_key_path.read_bytes(), password=None)
        ca_cert = x509.load_pem_x509_certificate(self.ca_cert_path.read_bytes())
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        builder = (
            x509.CertificateBuilder()
            .subject_name(_name(common_name))
            .issuer_name(ca_cert.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds))
        )
        if name == "server":
            builder = builder.add_extension(
                x509.SubjectAlternativeName(
                    [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
                ),
                critical=False,
            )
        cert = builder.sign(ca_key, hashes.SHA256())
        target = self.data_dir / "certs" / _safe_name(common_name)
        target.mkdir(parents=True, exist_ok=True)
        key_path = target / f"{name}.key"
        cert_path = target / f"{name}.crt"
        key_path.write_bytes(_private_key_bytes(key))
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        return IssuedCertificate(cert_path, key_path, common_name)


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _private_key_bytes(key) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def _safe_name(value: str) -> str:
    return "".join(item if item.isalnum() or item in {"-", "_", "."} else "_" for item in value)
