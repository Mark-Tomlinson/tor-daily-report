# Tor Daily Report

A Python script that queries your Tor relay's control port and emails you a health report. Run it via cron for daily, weekly, or monthly visibility into your relay's status.

## Features

- **Status overview**: Circuit health, connection count, uptime, Tor version
- **Relay identity**: Nickname, address, fingerprint
- **Consensus flags**: Guard, Stable, Fast, Valid, etc.
- **Traffic stats**: Total bytes read/written, average bandwidth since restart
- **Configurable alerts**: Warnings when connection count drops below thresholds
- **Email delivery**: Sends reports via SMTP with status emoji in subject line (✅ ⚠️ ❌)

## Sample Output

```
============================================================
  TOR RELAY REPORT: OnionPie
  Generated: 2026-02-03 08:00:00
  Host: onionpie
============================================================

STATUS
----------------------------------------
  Circuits:      ✅ Established
  Connections:   416
  Uptime:        8d 14h 33m 4s
  Tor Version:   0.4.8.21

RELAY IDENTITY
----------------------------------------
  Nickname:      OnionPie
  Address:       xxx.xxx.xxx.xxx:9001
  Fingerprint:   ABCD1234...

CONSENSUS FLAGS
----------------------------------------
  Fast, Running, Valid

TRAFFIC SINCE RESTART (01/26/2026 02:00)
----------------------------------------
  Read:          2.01 GB
  Written:       1.77 GB
  Avg Read:      2.84 KB/s
  Avg Write:     2.49 KB/s
```

## Requirements

- Python 3.6+
- [stem](https://stem.torproject.org/) - Tor controller library
- Access to your relay's control port (default: 9051)

## Installation

```bash
# Clone the repo
git clone https://github.com/Mark-Tomlinson/tor-daily-report.git
cd tor-daily-report

# Install dependencies
pip3 install -r requirements.txt
```

## Configuration

Edit the configuration section at the top of `tor-daily-report.py`:

```python
# Tor control port settings
TOR_CONTROL_HOST = "127.0.0.1"
TOR_CONTROL_PORT = 9051
TOR_CONTROL_PASSWORD = None  # Set if using password auth, otherwise uses cookie

# Email settings
SMTP_HOST = "smtp.mail.com"
SMTP_PORT = 587
SMTP_USERNAME = "your-email@example.com"
SMTP_PASSWORD = "your-password"
SMTP_USE_TLS = True

# Report settings
EMAIL_FROM = "your-email@example.com"
EMAIL_TO = "your-email@example.com"
RELAY_NICKNAME = "YourRelay"

# Alert thresholds
MIN_CONNECTIONS_WARN = 100  # Warning if fewer connections
MIN_CONNECTIONS_CRIT = 50   # Critical if fewer connections
```

### Control Port Access

Your Tor relay must have the control port enabled. In `/etc/tor/torrc`:

```
ControlPort 9051
CookieAuthentication 1
```

If running the script on the same machine as Tor (recommended), cookie authentication works automatically. For remote access, you'll need password authentication.

## Usage

```bash
# Test locally (prints to stdout)
python3 tor-daily-report.py --stdout

# Send report via email
python3 tor-daily-report.py
```

### Cron Examples

```bash
# Edit crontab
crontab -e

# Daily at 8am
0 8 * * * /usr/bin/python3 /path/to/tor-daily-report.py

# Weekly on Monday at 8am
0 8 * * 1 /usr/bin/python3 /path/to/tor-daily-report.py

# Monthly on the 1st at 8am
0 8 1 * * /usr/bin/python3 /path/to/tor-daily-report.py
```

## Complementary Tools

This script provides **trend monitoring** - periodic reports on relay health. For **immediate alerts** when your relay goes offline, consider also signing up for [Tor Weather](https://weather.torproject.org/), the Tor Project's official notification service.

| Tool | Purpose | Frequency |
|------|---------|-----------|
| Tor Weather | Relay offline alerts | Immediate |
| tor-daily-report | Health trends & stats | Daily/weekly/monthly |

## Resources

- [Tor Control Protocol Spec](https://spec.torproject.org/control-spec.html)
- [Stem Documentation](https://stem.torproject.org/)
- [Tor Relay Guide](https://community.torproject.org/relay/)

## License

MIT
