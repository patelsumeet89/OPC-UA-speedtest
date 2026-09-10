# OPC UA tag speed test

A small Python benchmark for measuring OPC UA read latency and tag throughput using `asyncua`.

## Install

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

## Secure endpoint setup

If your server advertises `Basic256Sha256` with `Sign` or `SignAndEncrypt`, this project can generate a test client certificate. Certificate files are not included in the repository. Generate one with:

```powershell
py .\generate_client_certificate.py
```

This creates `certs\client_cert.pem` and `certs\client_key.pem`. Have the OPC UA server administrator trust `certs\client_cert.pem`, then use the paths in the security string:

```powershell
--security-string "Basic256Sha256,Sign,certs/client_cert.pem,certs/client_key.pem"
```

The certificate is self-signed and intended for testing. Do not use it as a production certificate without following your server's certificate-management process.

## Run

Pass one or more OPC UA node IDs. The node ID syntax must match the server, for example `ns=2;s=Channel1.Device1.Tag1`.

```powershell
py .\opcua_speedtest.py `
  --endpoint opc.tcp://<host>:4840 `
  --username "<username>" `
  --password "<password>" `
  --security-string "Basic256Sha256,Sign,certs/client_cert.pem,certs/client_key.pem" `
  --node-id "ns=2;s=/Axis/Drive/AA_OFF_MODE" `
  --node-id "ns=2;s=/Axis/Drive/AC_FILTER_TIME" `
  --requests 500 `
  --warmup `
  --csv results.csv

If the server requires a secure endpoint, provide the policy, message mode, client certificate, and private key. The security string format is `Policy,MessageMode,ClientCertificate,PrivateKey`. Use the exact policy and message mode configured on the server. The server may also need to trust the client certificate.

The result reports total tags per second plus average, p50, p95, and maximum request latency. A request is one batch containing every `--node-id` value; the tags in a batch are read concurrently.

To test concurrent requests, increase both the worker count and concurrency deliberately:

```powershell
py .\opcua_speedtest.py --endpoint opc.tcp://localhost:4840 `
  --node-id "ns=2;s=Tag1" --node-id "ns=2;s=Tag2" `
  --requests 1000 --workers 4 --concurrency 4
```

py .\opcua_speedtest.py `
  --endpoint opc.tcp://<host>:4840 `
  --username "<username>" `
  --password "<password>" `
  --security-string "Basic256Sha256,Sign,certs/client_cert.pem,certs/client_key.pem" `
  --node-id "ns=2;s=/Axis/Drive/AA_OFF_MODE" `
  --node-id "ns=2;s=/Axis/Drive/AC_FILTER_TIME" `
  --requests 1000 `
  --workers 4 `
  --concurrency 4 `
  --warmup `
  --csv results-concurrent.csv
```

For authenticated servers, add `--username` and `--password`. Avoid putting real passwords in shell history; use an environment-aware wrapper for production testing.

## Interpretation

- `Throughput` is total values read divided by wall-clock test time.
- `Latency` is measured around all concurrent node reads in each batch.
- Start with `--workers 1 --concurrency 1`, then increase concurrency to find where server or network saturation begins.
- Compare runs with the same node count, request count, and server conditions.
