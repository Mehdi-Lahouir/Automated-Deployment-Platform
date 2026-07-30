# Production Readiness

v1.0 is a portfolio-grade release, not a claim of production certification. This
document defines the remaining controls, measurable acceptance criteria, and release
evidence needed before exposing the service to real users.

## Capacity and load targets

Use these as initial service-level objectives for the current project-sized workload;
revise them after measuring realistic traffic and data volumes.

| Measure | Initial target | Validation evidence |
|---|---:|---|
| Availability | 99.9% monthly | External probe and monthly report |
| API latency | p95 < 300 ms, p99 < 750 ms | Load-test report at steady state |
| Error rate | < 1% 5xx | Prometheus query during load test |
| Sustained traffic | 50 requests/second for 30 minutes | Test report with no SLO breach |
| Burst traffic | 100 requests/second for 5 minutes | Test report with bounded queueing |
| Recovery point objective | <= 24 hours | Snapshot timestamps and restore drill |
| Recovery time objective | < 15 minutes | Timed restore and application verification |

A production load test should use a dedicated environment, representative task-list
sizes, create/read/update/delete traffic, and the same database class intended for
production. Record the image digest, replica count, CPU/memory limits, database size,
tool configuration, latency percentiles, throughput, errors, and saturation. Do not
run destructive load against a shared or production database.

Pass only when the steady-state and burst targets hold, pods do not restart or
throttle materially, database connections remain below their limit, and latency
returns to baseline after the burst. Keep the report with the release evidence.

For a quick local baseline, install
[k6](https://grafana.com/docs/k6/latest/set-up/install-k6/), start the stack, and run:

```powershell
$env:APP_API_KEY = "the-value-from-your-env-file"
make load-test
```

The included one-minute scenario validates a 10-user read workload with a p95 below
500 ms and less than 1% errors. It is a development smoke test, not evidence that the
production targets above have been met.

## Identity, TLS, and secrets

The shared API key is sufficient only for a private demonstration. Before public
deployment:

- Put the service behind a managed HTTPS load balancer or ingress, redirect HTTP to
  HTTPS, require TLS 1.2 or later, automate certificate renewal, and test renewal and
  expiry alerts.
- Replace the shared key with an identity provider using short-lived tokens. Enforce
  server-side task ownership and role-based authorization, and audit privileged
  operations.
- Store application, database, Grafana, Restic, and object-storage credentials in a
  managed secret service. Synchronize them into workloads without committing secret
  values or plaintext secret manifests.
- Define rotation owners and intervals, test rotation without downtime, restrict
  workload access to individual secrets, and enable secret-access audit logs.
- Use a distributed gateway rate limiter, an application firewall where appropriate,
  and explicit trusted-proxy configuration.
- Pin deployable images by digest and third-party CI actions by commit SHA. Generate
  an SBOM, retain scan results, and establish a patching SLA.

Preserve the existing non-root/read-only containers, security contexts,
NetworkPolicies, log redaction, and least-privilege CI permissions.

## Cloud deployment decision

For the first production environment, prefer managed services over operating the
stateful stack in the application cluster:

| Concern | Recommended choice | Reason |
|---|---|---|
| Compute | Managed Kubernetes or a managed container service | Retains rolling deploys while reducing control-plane work |
| Database | Managed PostgreSQL with multi-zone availability and point-in-time recovery | Automated patching, failover, and durable backups |
| Images | Private regional container registry | Digest deployment, scanning, and shorter pulls |
| Edge | Managed load balancer, DNS, certificates, and WAF | Automated TLS and controlled public exposure |
| Secrets | Cloud secret manager with workload identity | No long-lived cloud keys in pods |
| Backups | Versioned object storage in a separate account/project and region | Survives cluster and primary-account failure |
| Observability | Managed metrics/logs, or a durable multi-node deployment | Avoids relying on the current single-node local stack |

Select a region based on user latency, data residency, service availability, and cost.
Provision environments with infrastructure as code, isolate production in its own
account/project, and use workload identity rather than static cloud credentials.
Maintain separate development, staging, and production configuration and approval
boundaries.

## Disaster-recovery validation

The existing verification restore proves that a snapshot is readable without
modifying the live database. Production readiness additionally requires a quarterly,
timed drill:

1. Record the incident start time, chosen snapshot, expected RPO, and responders.
2. Restore infrastructure in an isolated account/project or recovery region.
3. Recover managed PostgreSQL and, independently, verify the Restic/object-storage
   copy. Never assume a successful backup job implies a usable restore.
4. Deploy the exact released image digest and configuration, then run migrations.
5. Verify readiness, authentication and authorization, task CRUD, task ownership,
   metrics, logs, alerts, and a sampled data reconciliation.
6. Record achieved RPO/RTO, data discrepancies, manual steps, and failed assumptions.
7. Correct the runbook and repeat any failed stage.

Test loss of the cluster, database, region, secret access, and primary cloud account
over successive drills. Restrict and audit the live-replacement procedure, and
require explicit incident authorization before using it.

## v1.0 release checklist

### Code and database

- [ ] Lint, formatting, unit/integration tests, and browser smoke test pass
- [ ] Database migration upgrade succeeds from the previous release
- [ ] Migration downgrade or documented forward-fix procedure is tested
- [ ] Dependency audit and container scans meet the vulnerability policy
- [ ] Image digest and software bill of materials are recorded

### Deployment and operations

- [ ] Staging deploy uses the candidate image digest
- [ ] Readiness, liveness, dashboard, metrics, logs, and alert delivery are verified
- [ ] Rolling update and rollback are exercised
- [ ] Capacity targets pass with a saved load-test report
- [ ] On-call owner, escalation path, and operational runbook are current

### Security and recovery

- [ ] No placeholders or secrets exist in source, image layers, or release logs
- [ ] TLS, certificate renewal, identity, authorization, and rate limiting are tested
- [ ] Secret access and rotation are tested and audited
- [ ] Off-cluster backup completes and a verification restore passes
- [ ] Timed recovery drill meets the documented RPO and RTO

### Release

- [ ] User-visible changes and known limitations are documented
- [ ] Required approvals are recorded
- [ ] Commit is tagged `v1.0.0` and the tag resolves to the recorded image digest
- [ ] Post-deployment smoke tests pass
- [ ] Rollback window closes only after metrics and alerts remain healthy

Any unchecked production control is a known release risk and should have an owner,
deadline, and explicit acceptance. For a local portfolio release, the cloud-only
items may be marked not applicable, but should not be represented as completed.
