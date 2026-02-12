# Security Policy

## Scope
This service (`sigtrip-mcp-hub`) exposes an authenticated MCP endpoint and may process hotel search and booking-related user inputs.

## Supported Versions
Security fixes are applied to the latest deployed version.

## Reporting a Vulnerability
Please report vulnerabilities privately:
- Email: `security@sigtrip.com`
- Include: impact, reproduction steps, affected endpoints, and proof-of-concept

Do not open public issues for security vulnerabilities.

## Security Requirements

1. Authentication
- All production MCP access must be authenticated (gateway or service-level).
- Anonymous public access to `/sse` is not recommended.

2. Secrets
- Never commit secrets (`.env`, API keys, tokens).
- Store secrets in platform secret manager.
- Rotate `MCP_PROVIDER_SIGTRIP_API_KEY` regularly.

3. Transport
- Production traffic must use HTTPS.
- Do not expose plain HTTP publicly.

4. Logging
- Avoid logging credentials, payment data, or personal identifiers.
- Keep logs minimal and redact sensitive fields.

5. Rate Limiting and Abuse Protection
- Apply per-IP or per-token rate limits at edge/gateway.
- Add request size limits and timeout protections.

6. Dependency and Image Hygiene
- Keep base image and dependencies patched.
- Scan images/dependencies before release.

## Incident Response (Minimum)

1. Contain: restrict endpoint access and rotate secrets.
2. Assess: determine blast radius and affected data.
3. Mitigate: patch and redeploy.
4. Communicate: internal incident summary and timeline.
5. Prevent: add regression tests and monitoring rules.
