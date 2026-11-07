# `gh` TLS failure inside the Claude Code sandbox (#122)

## Symptom

On macOS, every `gh` call from a sandboxed Claude Code Bash call fails, even with `api.github.com` in `allowed_domains`:

```
tls: failed to verify certificate: x509: OSStatus -26276
```

`-26276` is `errSecInternalComponent`: the macOS Security framework could not finish the trust evaluation.

## Root cause

- The sandbox proxy is a plain `CONNECT` tunnel. It does not intercept TLS.
  - Sandboxed `curl -v https://api.github.com` shows the real GitHub chain (`CN=*.github.com`, issuer Sectigo) and `SSL certificate verify ok`.
  - No proxy CA bundle is set in the environment (`SSL_CERT_FILE`, `NODE_EXTRA_CA_CERTS` and similar are absent).
- `gh` is a Go program. On macOS, Go's `crypto/x509` hands verification to the Security framework (`SecTrustEvaluateWithError`), which talks to the `trustd` service over XPC.
- The Seatbelt sandbox profile blocks that service. The same evaluation fails without Go:
  - Outside the sandbox, `security verify-cert -c chain.pem -p ssl -s api.github.com` reports CT status `verified`.
  - Inside the sandbox, the same command reports CT status `not verified` (`Unable to find at least 2 signed certificate timestamps`), because it cannot reach the trust service and its data.
- `curl` and Python work because they verify with their own CA file (LibreSSL / OpenSSL), not with `trustd`.

The cause is the sandbox profile, not the allowlist and not a proxy CA.

## What does not work

- `SSL_CERT_FILE=/etc/ssl/cert.pem gh ...`: Go on macOS ignores `SSL_CERT_FILE`.
- `GODEBUG=x509usefallbackroots=1`: fallback roots apply only when no platform verifier exists; macOS always has one.
- Adding hosts to `allowed_domains`: the connection already succeeds; verification fails afterward.

## Hosts `gh` contacts

- `api.github.com` (REST and GraphQL).
- `cafe.github.com`: a second violation names this host. Its purpose was not confirmed (likely `gh` telemetry). Whether issue and PR commands need it is untested; add it only if a call fails without it.

## Workarounds (no settings change)

1. Run `gh` and `git push` (HTTPS) with the sandbox disabled for that one call (`dangerouslyDisableSandbox: true`). This is the current practice.
2. Use the GitHub MCP tools (`mcp__plugin_github_github__*`) for issue and PR reads and writes. They run outside the Bash sandbox.
3. Plain `git` over HTTPS does not use the Security framework for TLS: a sandboxed `git ls-remote origin` with `allowed_domains: ["github.com"]` succeeds. A push still needs credentials; if the credential helper is `gh auth git-credential`, that helper is a Go program and may hit the same failure, so push with the sandbox off. A `git worktree add` needs the sandbox off for a different reason: the sandbox denies writes to `.git/config`.

## Fix (operator settings change)

Claude Code has a macOS-only sandbox setting that allows the trust service: `sandbox.enableWeakerNetworkIsolation: true` in `~/.claude/settings.json`. It lets Go tools such as `gh`, `gcloud` and `terraform` verify certificates inside the sandbox. It weakens isolation slightly, because the sandboxed process can then reach `trustd`.

Alternative: `sandbox.excludedCommands: ["gh"]` runs `gh` outside the sandbox every time.

Neither change is applied by this repository. After the operator applies one, verify with a sandboxed `gh api /rate_limit` with `allowed_domains: ["api.github.com"]`.
