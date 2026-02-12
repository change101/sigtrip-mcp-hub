# Privacy Notice (Service-Level Draft)

Status: Draft template for internal/legal review.

## Overview
SigTrip llc. may process data submitted through this MCP service to provide hotel search, comparison, and booking handoff functionality.

## Data Categories (Potential)
- Query inputs: location, dates, guest count, free-text instructions
- Booking payload fields: guest name, email, phone, check-in/check-out, room/offer IDs
- Technical telemetry: timestamps, request IDs, error metadata, service diagnostics

## Data Sources
- Data received from clients (aggregators/agents)
- Data received from upstream provider integrations (e.g., hotel supplier MCPs)

## Purpose of Processing
- Fulfill hotel search/comparison/booking requests
- Service reliability, monitoring, and security
- Abuse prevention and incident response

## Data Sharing
- Upstream providers receive only required fields for each operation.
- Infrastructure providers (hosting, logging, observability) may process operational data.

## Data Retention
- Define and document retention windows by data type (to be finalized by legal/security).
- Do not retain booking payloads longer than operationally necessary.

## Security Controls
- Encryption in transit (HTTPS)
- Access controls and secret management
- Logging minimization and redaction

## User Rights / Compliance
Depending on jurisdiction, users may have rights (access, deletion, correction, portability).
Define your compliance workflow and response SLAs.

## Contacts
- Privacy contact: `privacy@sigtrip.com`
- Security contact: `security@sigtrip.com`

## Legal Review Required
This file is not legal advice and must be reviewed by legal counsel before publication.
