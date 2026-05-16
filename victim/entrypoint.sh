#!/bin/sh
set -e

mkdir -p /certs

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout /certs/server.key \
  -out    /certs/server.crt \
  -days   365 \
  -subj   "/CN=victim" \
  -addext "subjectAltName=IP:172.20.0.10"

exec python server.py
