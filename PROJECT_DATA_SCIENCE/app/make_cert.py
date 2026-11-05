"""Create a self-signed certificate so the Streamlit app can be served over HTTPS on this machine.

Writes certs/localhost.crt and certs/localhost.key next to the app (PROJECT_DATA_SCIENCE/certs/).
run_app.bat calls this automatically; it only rewrites the files when they are missing or do not
cover every name in HOSTNAMES. The certificate is valid for https://agrorestoreai (the name that
setup_hostname.bat points at this machine), localhost and 127.0.0.1, for 10 years.
Browsers show a one-time warning for a self-signed certificate: choose "Advanced" -> "Proceed", or
run trust_cert.bat once to add the certificate to the Windows trusted root store.
"""

import datetime as dt
import ipaddress
import sys
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

APP_HOSTNAME = "agrorestoreai"                       # https://agrorestoreai -> this machine (hosts file)
HOSTNAMES = [APP_HOSTNAME, "localhost"]
CERT_DIR = Path(__file__).resolve().parent.parent / "certs"
CERT_FILE = CERT_DIR / "localhost.crt"
KEY_FILE = CERT_DIR / "localhost.key"


def cert_covers_hostnames() -> bool:
    """True if the existing certificate lists every name in HOSTNAMES."""
    try:
        cert = x509.load_pem_x509_certificate(CERT_FILE.read_bytes())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        names = set(san.get_values_for_type(x509.DNSName))
        return all(h in names for h in HOSTNAMES)
    except Exception:
        return False


def make_cert(force: bool = False) -> None:
    if CERT_FILE.exists() and KEY_FILE.exists() and not force and cert_covers_hostnames():
        print(f"Certificate already exists and covers {', '.join(HOSTNAMES)}: {CERT_FILE}")
        return
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, APP_HOSTNAME),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AgroRestore AI (local development)"),
    ])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(h) for h in HOSTNAMES]
                + [x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                   x509.IPAddress(ipaddress.IPv6Address("::1"))]
            ),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    KEY_FILE.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ))
    CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print(f"Certificate written for {', '.join(HOSTNAMES)}: {CERT_FILE}\nPrivate key written: {KEY_FILE}")


if __name__ == "__main__":
    make_cert(force="--force" in sys.argv)
