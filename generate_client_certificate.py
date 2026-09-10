#!/usr/bin/env python3
"""Generate a self-signed client certificate for OPC UA testing."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


output_dir = Path("certs")
output_dir.mkdir(exist_ok=True)

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
subject = issuer = x509.Name(
    [
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "OPC UA Speed Test"),
        x509.NameAttribute(NameOID.COMMON_NAME, "OPC UA Speed Test Client"),
    ]
)
now = datetime.now(timezone.utc)
certificate = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(private_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(now - timedelta(minutes=5))
    .not_valid_after(now + timedelta(days=365))
    .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
    .add_extension(
        x509.SubjectAlternativeName(
            [
                x509.UniformResourceIdentifier("urn:example.org:FreeOpcUa:opcua-asyncio"),
                x509.DNSName("CABOLLT5057"),
            ]
        ),
        critical=False,
    )
    .add_extension(
        x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH]),
        critical=False,
    )
    .sign(private_key, hashes.SHA256())
)

(output_dir / "client_key.pem").write_bytes(
    private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
)
(output_dir / "client_cert.pem").write_bytes(
    certificate.public_bytes(serialization.Encoding.PEM)
)
print("Created certs/client_cert.pem")
print("Created certs/client_key.pem")
print("Ask the OPC UA server administrator to trust client_cert.pem.")
