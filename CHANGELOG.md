# Changelog

## [1.2.0] - 2026-08-15
### Added
- IPv6 support (dual‑stack)
- DNS‑over‑TLS and DNSSEC toggle
- Syslog integration
- Health check endpoint (`/var/run/dnsfrenzy/health`)
- Graceful shutdown (SIGTERM/SIGINT)
- Network change detection
- Auto‑upgrade script (`dnsfrenzy-upgrade`)
- Config preserved in `/etc/dnsfrenzy/config.json`

### Fixed
- Latency parsing (integer values)
- Global DNS sync for VPN compatibility
- Health directory creation

## [1.1.1] - 2026-08-15
### Added
- Initial release
- Smart mixing, blacklisting, multi‑interface
- Historical logging
- Management commands
