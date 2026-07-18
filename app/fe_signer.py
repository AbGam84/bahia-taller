"""
Katire — Firma XAdES-EPES para comprobantes electrónicos Hacienda CR.

Usa certificado .p12 (PKCS#12) del emisor + política de firma de la DGT.
"""

from __future__ import annotations

from pathlib import Path

from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, pkcs12
from lxml import etree

# Política de firma reconocida por ATV / Hacienda CR (Resolución DGT)
CR_POLICY_ID = (
    "https://www.hacienda.go.cr/ATV/ComprobanteElectronico/docs/esquemas/"
    "2016/v4.3/ResolucionComprobantesElectronicosDGT-R-48-2016_Firmado.pdf"
)
CR_POLICY_DIGEST_B64 = "0hUOjdNR9k/TvWzFByGZza6JWKNRE4mUuX3HjZbjWxg="


def load_p12(p12_path: Path | str, password: str):
    raw = Path(p12_path).read_bytes()
    pwd = password.encode("utf-8") if password else None
    key, cert, _extra = pkcs12.load_key_and_certificates(raw, pwd)
    if key is None or cert is None:
        raise ValueError("El archivo .p12 no contiene llave privada y certificado válidos")
    key_pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    cert_pem = cert.public_bytes(Encoding.PEM)
    return key_pem, cert_pem


def sign_fe_xml(xml_content: str, p12_path: Path | str, password: str) -> str:
    """
    Firma el XML del comprobante (enveloped XAdES-EPES) y devuelve XML firmado.
    """
    if not xml_content or not xml_content.strip():
        raise ValueError("XML vacío; no se puede firmar")
    if not Path(p12_path).exists():
        raise ValueError("No se encontró el certificado .p12 en el servidor")

    from signxml import DigestAlgorithm
    from signxml.xades import XAdESDataObjectFormat, XAdESSignaturePolicy, XAdESSigner

    key_pem, cert_pem = load_p12(p12_path, password)
    # Quitar declaración XML suelta para parseo estable; se reinserta al serializar
    cleaned = xml_content.strip()
    if cleaned.startswith("<?xml"):
        cleaned = cleaned.split("?>", 1)[-1].strip()

    root = etree.fromstring(cleaned.encode("utf-8"))
    # Hacienda espera la firma como último hijo del nodo raíz del comprobante
    policy = XAdESSignaturePolicy(
        Identifier=CR_POLICY_ID,
        Description="Politica de Firma de Comprobantes Electronicos de Costa Rica",
        DigestMethod=DigestAlgorithm.SHA256,
        DigestValue=CR_POLICY_DIGEST_B64,
    )
    data_fmt = XAdESDataObjectFormat(
        Description="ComprobanteElectronico",
        MimeType="text/xml",
    )
    signer = XAdESSigner(
        signature_policy=policy,
        claimed_roles=["Emisor"],
        data_object_format=data_fmt,
        c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
    )
    signed = signer.sign(root, key=key_pem, cert=cert_pem)
    out = etree.tostring(signed, encoding="utf-8", xml_declaration=True)
    text = out.decode("utf-8")
    if "Signature" not in text and "ds:Signature" not in text:
        raise RuntimeError("La firma no se insertó en el XML")
    return text


def try_validate_p12(p12_path: Path | str, password: str) -> dict:
    key_pem, cert_pem = load_p12(p12_path, password)
    from cryptography import x509

    cert = x509.load_pem_x509_certificate(cert_pem)
    subject = cert.subject.rfc4514_string()
    return {
        "ok": True,
        "subject": subject,
        "not_valid_after": cert.not_valid_after_utc.isoformat()
        if hasattr(cert, "not_valid_after_utc")
        else str(cert.not_valid_after),
    }
