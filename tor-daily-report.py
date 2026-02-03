#!/usr/bin/env python3
"""
Tor Relay Daily Report
Generates and emails a health report for your Tor relay.

Requirements:
    pip install stem

Usage:
    python3 tor-daily-report.py           # Send report via email
    python3 tor-daily-report.py --stdout  # Print to stdout (for testing)

Cron examples:
    # Daily at 8am
    0 8 * * * /usr/bin/python3 /home/pi/tor-daily-report.py

    # Weekly on Monday at 8am
    0 8 * * 1 /usr/bin/python3 /home/pi/tor-daily-report.py
"""

import argparse
import smtplib
import socket
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from stem.control import Controller

# =============================================================================
# CONFIGURATION
# =============================================================================

# Tor control port settings
TOR_CONTROL_HOST = "127.0.0.1"
TOR_CONTROL_PORT = 9051
TOR_CONTROL_PASSWORD = None  # Set if using password auth, otherwise uses cookie

# Email settings (Mail.com SMTP)
SMTP_HOST = "smtp.mail.com"
SMTP_PORT = 587  # TLS
SMTP_USERNAME = "tor.relay@activist.com"
SMTP_PASSWORD = "YOUR_PASSWORD_HERE"  # TODO: Set your password
SMTP_USE_TLS = True

# Report settings
EMAIL_FROM = "tor.relay@activist.com"
EMAIL_TO = "tor.relay@activist.com"  # Send to yourself, or change as needed
RELAY_NICKNAME = "OnionPie"  # For the subject line

# Alert thresholds
MIN_CONNECTIONS_WARN = 100  # Warn if fewer connections than this
MIN_CONNECTIONS_CRIT = 50   # Critical if fewer than this

# =============================================================================
# REPORT GENERATION
# =============================================================================

def format_bytes(num_bytes):
    """Format bytes into human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.2f} PB"


def format_duration(seconds):
    """Format seconds into human-readable duration."""
    days, remainder = divmod(int(seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def get_relay_report():
    """Connect to Tor control port and gather relay statistics."""
    report = {
        "generated": datetime.now(),
        "hostname": socket.gethostname(),
        "warnings": [],
        "errors": [],
    }

    try:
        with Controller.from_port(address=TOR_CONTROL_HOST, port=TOR_CONTROL_PORT) as controller:
            # Authenticate
            if TOR_CONTROL_PASSWORD:
                controller.authenticate(password=TOR_CONTROL_PASSWORD)
            else:
                controller.authenticate()  # Cookie auth

            # Basic info
            report["version"] = controller.get_version().version_str
            report["uptime_seconds"] = int(controller.get_info("uptime"))
            report["uptime_human"] = format_duration(report["uptime_seconds"])

            # Traffic stats
            report["bytes_read"] = int(controller.get_info("traffic/read"))
            report["bytes_written"] = int(controller.get_info("traffic/written"))
            report["traffic_read_human"] = format_bytes(report["bytes_read"])
            report["traffic_written_human"] = format_bytes(report["bytes_written"])

            # Relay identity
            report["fingerprint"] = controller.get_info("fingerprint")
            report["nickname"] = controller.get_conf("Nickname", RELAY_NICKNAME)
            report["address"] = controller.get_info("address", "unknown")
            report["or_port"] = controller.get_conf("ORPort", "9001")

            # Circuit status
            report["circuits_established"] = controller.get_info("status/circuit-established") == "1"

            # Count OR connections (other relays)
            orconn_status = controller.get_info("orconn-status", "")
            connections = [line for line in orconn_status.strip().split("\n") if line]
            report["connection_count"] = len(connections)

            # Check connection thresholds
            if report["connection_count"] < MIN_CONNECTIONS_CRIT:
                report["warnings"].append(
                    f"⚠️  CRITICAL: Only {report['connection_count']} connections "
                    f"(threshold: {MIN_CONNECTIONS_CRIT})"
                )
            elif report["connection_count"] < MIN_CONNECTIONS_WARN:
                report["warnings"].append(
                    f"⚠️  WARNING: Only {report['connection_count']} connections "
                    f"(threshold: {MIN_CONNECTIONS_WARN})"
                )

            # Get relay flags from consensus
            try:
                ns = controller.get_network_status(report["fingerprint"])
                report["flags"] = list(ns.flags) if ns.flags else []
                report["bandwidth"] = ns.bandwidth  # Consensus bandwidth
                report["published"] = ns.published
            except Exception as e:
                report["flags"] = ["(unable to retrieve)"]
                report["errors"].append(f"Could not get network status: {e}")

            # Check for expected flags
            expected_flags = {"Running", "Valid"}
            if report.get("flags") and isinstance(report["flags"], list):
                current_flags = set(report["flags"])
                missing = expected_flags - current_flags
                if missing:
                    report["warnings"].append(
                        f"⚠️  Missing expected flags: {', '.join(missing)}"
                    )

            # Accounting info (if configured)
            try:
                accounting_enabled = controller.get_info("accounting/enabled", "0")
                if accounting_enabled == "1":
                    report["accounting"] = {
                        "bytes_left": controller.get_info("accounting/bytes-left"),
                        "interval_end": controller.get_info("accounting/interval-end"),
                    }
            except:
                pass

    except Exception as e:
        report["errors"].append(f"Failed to connect to Tor control port: {e}")

    return report


def format_report_text(report):
    """Format the report as plain text for email."""
    lines = []

    # Header
    lines.append("=" * 60)
    lines.append(f"  TOR RELAY REPORT: {report.get('nickname', 'Unknown')}")
    lines.append(f"  Generated: {report['generated'].strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Host: {report.get('hostname', 'unknown')}")
    lines.append("=" * 60)
    lines.append("")

    # Warnings section (if any)
    if report.get("warnings"):
        lines.append("ALERTS")
        lines.append("-" * 40)
        for warning in report["warnings"]:
            lines.append(warning)
        lines.append("")

    # Errors section (if any)
    if report.get("errors"):
        lines.append("ERRORS")
        lines.append("-" * 40)
        for error in report["errors"]:
            lines.append(f"❌ {error}")
        lines.append("")
        # If we had connection errors, not much else to show
        if "Failed to connect" in str(report["errors"]):
            return "\n".join(lines)

    # Status
    lines.append("STATUS")
    lines.append("-" * 40)
    circuit_status = "✅ Established" if report.get("circuits_established") else "❌ NOT Established"
    lines.append(f"  Circuits:      {circuit_status}")
    lines.append(f"  Connections:   {report.get('connection_count', 'N/A')}")
    lines.append(f"  Uptime:        {report.get('uptime_human', 'N/A')}")
    lines.append(f"  Tor Version:   {report.get('version', 'N/A')}")
    lines.append("")

    # Relay Identity
    lines.append("RELAY IDENTITY")
    lines.append("-" * 40)
    lines.append(f"  Nickname:      {report.get('nickname', 'N/A')}")
    lines.append(f"  Address:       {report.get('address', 'N/A')}:{report.get('or_port', 'N/A')}")
    lines.append(f"  Fingerprint:   {report.get('fingerprint', 'N/A')}")
    lines.append("")

    # Flags
    lines.append("CONSENSUS FLAGS")
    lines.append("-" * 40)
    flags = report.get("flags", [])
    if flags:
        lines.append(f"  {', '.join(flags)}")
    else:
        lines.append("  (none)")
    lines.append("")

    # Traffic - calculate restart time from uptime
    uptime = report.get("uptime_seconds", 0)
    if uptime > 0:
        restart_time = report["generated"] - timedelta(seconds=uptime)
        restart_str = restart_time.strftime("%m/%d/%Y %H:%M")
        lines.append(f"TRAFFIC SINCE RESTART ({restart_str})")
    else:
        lines.append("TRAFFIC SINCE RESTART")
    lines.append("-" * 40)
    lines.append(f"  Read:          {report.get('traffic_read_human', 'N/A')}")
    lines.append(f"  Written:       {report.get('traffic_written_human', 'N/A')}")

    # Calculate average bandwidth if uptime > 0
    if uptime > 0:
        avg_read = report.get("bytes_read", 0) / uptime
        avg_write = report.get("bytes_written", 0) / uptime
        lines.append(f"  Avg Read:      {format_bytes(avg_read)}/s")
        lines.append(f"  Avg Write:     {format_bytes(avg_write)}/s")
    lines.append("")

    # Footer
    lines.append("-" * 60)
    lines.append("Relay search: https://metrics.torproject.org/rs.html#details/" +
                 report.get("fingerprint", ""))
    lines.append("")

    return "\n".join(lines)


def send_email(subject, body):
    """Send the report via email."""
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    try:
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)

        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Tor Relay Daily Report")
    parser.add_argument("--stdout", action="store_true",
                        help="Print report to stdout instead of emailing")
    args = parser.parse_args()

    # Generate the report
    report = get_relay_report()
    report_text = format_report_text(report)

    # Determine subject line
    if report.get("warnings"):
        status_emoji = "⚠️"
    elif report.get("errors"):
        status_emoji = "❌"
    else:
        status_emoji = "✅"

    subject = f"{status_emoji} Tor Relay Report: {report.get('nickname', RELAY_NICKNAME)}"

    if args.stdout:
        print(report_text)
    else:
        if send_email(subject, report_text):
            print(f"Report sent to {EMAIL_TO}")
        else:
            # Fallback: print to stdout so cron captures it
            print("Email failed, dumping report:")
            print(report_text)


if __name__ == "__main__":
    main()
