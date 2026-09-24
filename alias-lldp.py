#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# alias-lldp.py – LLDP-based interface alias automation for AOS switches
# Works on systems without the "cli" module (subprocess shell=True)
#
# Copyright (c) 2026 Dominik Gawin
# SPDX-License-Identifier: MIT
#

import subprocess
import re
import sys


# -----------------------------------------------------------
# Helper functions
# -----------------------------------------------------------

def run_cli(cmd: str) -> str:
    """Run a CLI command and return its output."""
    result = subprocess.run(
        [cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True
    )
    return result.stdout.decode("utf-8", errors="replace")


def port_key(port: str):
    """Sort key for ports: 1/1/2 before 1/1/10."""
    return [int(p) for p in port.split("/")]


def sanitize_alias(alias: str) -> str:
    """
    Allow only safe characters. The alias is built from LLDP data sent by
    the neighbor device and inserted into a shell command – without this
    filter, a crafted system name could execute arbitrary commands.
    """
    return re.sub(r"[^A-Za-z0-9._-]", "_", alias)


# -----------------------------------------------------------
# LLDP parser – output format of 'show lldp remote-system'
# -----------------------------------------------------------

def parse_lldp():
    """
    Read LLDP neighbors.
    Returns:
    {
        "1/1/6": {"sysname": "fritz.box", "portdesc": "LAN:3"},
        "1/1/22": {"sysname": "AP-02", "portdesc": "... eth0"},
        ...
    }
    """
    out = run_cli("show lldp remote-system")
    neighbors = {}
    current_port = None

    for line in out.splitlines():
        line = line.strip()

        # Detect start of a neighbor block
        # Example: Remote LLDP nearest-bridge Agents on Local Port 1/1/6:
        if line.startswith("Remote LLDP") and "Local Port" in line:
            parts = line.split()
            current_port = parts[-1].replace(":", "")  # "1/1/6"
            neighbors[current_port] = {"sysname": "--", "portdesc": "--", "sysdesc": "--"}
            continue

        # Port Description
        if line.startswith("Port Description"):
            if "=" in line:
                desc = line.split("=", 1)[1].strip().rstrip(",")
            else:
                desc = line.replace("Port Description", "").strip()

            if desc == "(null)":
                desc = "--"

            if current_port:
                neighbors[current_port]["portdesc"] = desc
            continue

        # System Name
        if line.startswith("System Name"):
            if "=" in line:
                sysname = line.split("=", 1)[1].strip().rstrip(",")
            else:
                sysname = line.replace("System Name", "").strip()

            if sysname == "(null)":
                sysname = "--"

            if current_port:
                neighbors[current_port]["sysname"] = sysname
            continue

        # System Description
        if line.startswith("System Description"):
            if "=" in line:
                sysdesc = line.split("=", 1)[1].strip().rstrip(",")
            else:
                sysdesc = line.replace("System Description", "").strip()

            if sysdesc == "(null)":
                sysdesc = "--"

            if current_port:
                neighbors[current_port]["sysdesc"] = sysdesc
            continue

    return neighbors


# -----------------------------------------------------------
# Read existing aliases
# -----------------------------------------------------------

def parse_aliases():
    """
    Parse the output of 'show interfaces alias'
    and return {port: alias}.
    """
    out = run_cli("show interfaces alias")
    aliases = {}

    for line in out.splitlines():
        line = line.strip()

        # Pattern: 1/1/6 ... "AliasName"
        m = re.match(r"^([0-9]+/[0-9]+/[0-9]+)\s+.*?\"(.*)\"$", line)
        if m:
            aliases[m.group(1)] = m.group(2).strip()
            continue

        # Fallback: port without alias
        m2 = re.match(r"^([0-9]+/[0-9]+/[0-9]+)\s+", line)
        if m2:
            aliases.setdefault(m2.group(1), "")

    return aliases


# -----------------------------------------------------------
# Link type detection (uplink)
# -----------------------------------------------------------

def is_uplink(name: str) -> bool:
    """Detect OmniSwitch uplinks."""
    if not name or name == "--":
        return False

    keywords = ["OS"]
    for k in keywords:
        if re.search(k, name, re.IGNORECASE):
            return True
    return False

# -----------------------------------------------------------
# Link type detection (access point)
# -----------------------------------------------------------

def is_ap(name: str) -> bool:
    """Detect OmniAccess Stellar (OAW) access points."""
    if not name or name == "--":
        return False

    keywords = ["OAW-"]
    for k in keywords:
        if re.search(k, name, re.IGNORECASE):
            return True
    return False

# -----------------------------------------------------------
# Alias proposal
# -----------------------------------------------------------

def propose_alias(sysname: str, portdesc: str, sysdesc: str) -> str:
    if not sysname or sysname == "--":
        return ""

    prefix = ""

    # Uplink?
    if is_uplink(sysdesc):
        prefix = "UPLINK-"

    # Access point?
    if is_ap(sysdesc):
        prefix = "OAW-"

    suffix = ""

    # Derive suffix from the port description
    if portdesc and portdesc != "--":
        clean = portdesc.replace(" ", "_")
        clean = clean.replace(":", "")  # LAN:3 -> LAN3
        parts = clean.split("_")

        # use the last meaningful part (e.g. eth0)
        last = parts[-1]
        suffix = "_" + last

    return sanitize_alias(f"{prefix}{sysname}{suffix}")


# -----------------------------------------------------------
# Set alias
# -----------------------------------------------------------

def set_alias(port: str, alias: str, dry_run: bool):
    alias = sanitize_alias(alias)
    if dry_run:
        print(f"[DRY-RUN] would set: {port} → \"{alias}\"")
        return

    cmd = f"interface {port} alias \"{alias}\""
    run_cli(cmd)
    print(f"[SET] {port} → \"{alias}\"")


# -----------------------------------------------------------
# Main program
# -----------------------------------------------------------

def main():
    dry_run = "--dry-run" in sys.argv
    auto = "--auto" in sys.argv

    print("Reading LLDP neighbors...")
    lldp = parse_lldp()

    print("Reading existing aliases...")
    aliases = parse_aliases()

    apply_all = False
    skip_all = False

    for port in sorted(aliases.keys(), key=port_key):
        info = lldp.get(port, {"sysname": "--", "portdesc": "--", "sysdesc": "--"})
        sysname = info["sysname"]
        portdesc = info["portdesc"]
        sysdesc = info["sysdesc"]

        new_alias = propose_alias(sysname, portdesc, sysdesc)
        old_alias = aliases.get(port, "")

        if not new_alias:
            #print(f"{port}: no neighbor -> skipping")
            continue

        print("--------------------------------------------------")
        print(f"Port:           {port}")
        print(f"LLDP SysName:   {sysname}")
        print(f"LLDP SysDescr:  {sysdesc}")
        print(f"LLDP PortDescr: {portdesc}")
        print(f"Current alias:  '{old_alias}'")
        print(f"New alias:      '{new_alias}'")

        if new_alias == old_alias:
            print("-> Alias already correct, no change.")
            continue

        # Auto/skip handling
        if skip_all:
            continue
        if apply_all or auto:
            set_alias(port, new_alias, dry_run)
            continue

        choice = input("[y] set / [n] keep / [a] set all / [s] skip all: ").strip().lower()
        if choice == "y":
            set_alias(port, new_alias, dry_run)
        elif choice == "n":
            pass
        elif choice == "a":
            apply_all = True
            set_alias(port, new_alias, dry_run)
        elif choice == "s":
            skip_all = True
            print("Skipping all remaining ports.")
        else:
            print("Invalid input -> skipping.")

    print("Done.")


if __name__ == "__main__":
    main()