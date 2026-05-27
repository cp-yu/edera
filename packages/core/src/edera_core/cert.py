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
    cert_pem: str
    key_pem: str
    ca_pem: str
    common_name: str


@dataclass(frozen=True)
class ServerCertificate:
    cert_path: Path
    key_path: Path


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
        _write_private_key(self.ca_key_path, _private_key_bytes(key))
        self.ca_cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    def issue_client(self, common_name: str, ttl_seconds: int = 3600) -> IssuedCertificate:
        cert_pem, key_pem = self._issue_pem(common_name, ttl_seconds)
        return IssuedCertificate(
            cert_pem.decode(),
            key_pem.decode(),
            self.ca_cert_pem().decode(),
            common_name,
        )

    def issue_server(
        self,
        listen_address: str = "localhost",
        common_name: str = "rig-daemon",
        ttl_seconds: int = 365 * 24 * 3600,
    ) -> ServerCertificate:
        self.ensure()
        cert_path = self.data_dir / "server.crt"
        key_path = self.data_dir / "server.key"
        if cert_path.exists() and key_path.exists():
            return ServerCertificate(cert_path, key_path)
        cert_pem, key_pem = self._issue_pem(common_name, ttl_seconds, _server_alt_names(listen_address))
        _write_private_key(key_path, key_pem)
        cert_path.write_bytes(cert_pem)
        return ServerCertificate(cert_path, key_path)

    def ca_cert_pem(self) -> bytes:
        self.ensure()
        return self.ca_cert_path.read_bytes()

    def _issue_pem(
        self,
        common_name: str,
        ttl_seconds: int,
        alt_names: list[x509.GeneralName] | None = None,
    ) -> tuple[bytes, bytes]:
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
        if alt_names:
            builder = builder.add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        cert = builder.sign(ca_key, hashes.SHA256())
        return cert.public_bytes(serialization.Encoding.PEM), _private_key_bytes(key)


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _private_key_bytes(key) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def _write_private_key(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    path.chmod(0o600)


def _server_alt_names(listen_address: str) -> list[x509.GeneralName]:
    host = listen_address.rsplit(":", 1)[0] if ":" in listen_address else listen_address
    host = host.strip("[]") or "localhost"
    names: list[x509.GeneralName] = [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
    if host not in {"localhost", "127.0.0.1", "0.0.0.0", "::"}:
        try:
            names.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            names.append(x509.DNSName(host))
    return names
