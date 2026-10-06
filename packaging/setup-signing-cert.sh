#!/bin/bash
# Creates a local self-signed code-signing certificate in the login keychain.
#
# Why: macOS ties the Accessibility / Input Monitoring grant to the app's code
# signature. Ad-hoc signing (`codesign --sign -`) yields a different identity on
# every build, so the grant breaks after each reinstall. Signing with this
# certificate keeps the identity stable across rebuilds on this Mac.
#
# The private key never leaves this machine's login keychain. Safe to re-run:
# it does nothing when the identity already exists.
set -euo pipefail

CERT_NAME="${SIGNING_IDENTITY:-MySuperWhisper Local Signing}"
KEYCHAIN="$HOME/Library/Keychains/login.keychain-db"

if security find-identity -v -p codesigning | grep -q "\"$CERT_NAME\""; then
    echo "Signing identity '$CERT_NAME' already exists."
    exit 0
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
P12_PASSWORD="mysuperwhisper-temp"

# /usr/bin/openssl (LibreSSL) writes a .p12 that `security import` accepts;
# Homebrew's OpenSSL 3 needs extra flags for that.
/usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
    -keyout "$WORK_DIR/key.pem" -out "$WORK_DIR/cert.pem" \
    -subj "/CN=$CERT_NAME" \
    -addext "keyUsage=critical,digitalSignature" \
    -addext "extendedKeyUsage=critical,codeSigning" 2>/dev/null \
  || /usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
    -keyout "$WORK_DIR/key.pem" -out "$WORK_DIR/cert.pem" \
    -subj "/CN=$CERT_NAME" \
    -config <(printf '[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=%s\n[ext]\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=critical,codeSigning\n' "$CERT_NAME")

/usr/bin/openssl pkcs12 -export -inkey "$WORK_DIR/key.pem" -in "$WORK_DIR/cert.pem" \
    -out "$WORK_DIR/identity.p12" -passout "pass:$P12_PASSWORD"

security import "$WORK_DIR/identity.p12" -k "$KEYCHAIN" -P "$P12_PASSWORD" -T /usr/bin/codesign

# Trust the certificate for code signing (macOS asks for your password once).
security add-trusted-cert -r trustRoot -p codeSign -k "$KEYCHAIN" "$WORK_DIR/cert.pem"

if security find-identity -v -p codesigning | grep -q "\"$CERT_NAME\""; then
    echo "Created signing identity '$CERT_NAME'."
else
    echo "Identity was imported but is not yet valid for code signing." >&2
    exit 1
fi
