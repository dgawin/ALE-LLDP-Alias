# ALE-Alias

Python script that **automatically sets interface aliases on Alcatel-Lucent
Enterprise OmniSwitches (AOS) based on their LLDP neighbors**.

For every port with an LLDP neighbor, an alias is proposed from the
neighbor's system name and port description, for example:

| Neighbor                             | Proposed alias           |
|--------------------------------------|--------------------------|
| OmniSwitch `CORE-SW1`, port `1/1/49` | `UPLINK-CORE-SW1_1_1_49` |
| Access point `AP-EG-01`, `eth0`      | `OAW-AP-EG-01_eth0`      |
| Router `fritz.box`, `LAN:3`          | `fritz.box_LAN3`         |

For security reasons, every character outside `A-Z a-z 0-9 . _ -` is
replaced with `_`.

- **`UPLINK-`**: neighbor is an OmniSwitch (system description contains `OS`)
- **`OAW-`**: neighbor is an OmniAccess Stellar AP (system description contains `OAW-`)

## Requirements

- ALE OmniSwitch running AOS 8.x with Python 3 on the switch (tested on AOS 8.10R2)
- LLDP enabled on the relevant ports

The script runs the CLI commands `show lldp remote-system`,
`show interfaces alias` and `interface <port> alias "<alias>"` directly
through the switch shell.

## Usage

Copy the script to the switch (e.g. via SCP to `/flash/python/`) and run
it there:

```sh
python3 alias-lldp.py --dry-run   # show proposals only, change nothing
python3 alias-lldp.py             # confirm each port interactively
python3 alias-lldp.py --auto      # apply all proposals without asking
```

Interactive mode:

| Key | Action                                 |
|-----|----------------------------------------|
| `y` | set the alias for this port            |
| `n` | keep this port unchanged               |
| `a` | set this and all remaining ports       |
| `s` | skip all remaining ports               |

### Example: dry run

```
SW-01> python3 ./alias-lldp.py --dry-run
Reading LLDP neighbors...
Reading existing aliases...
--------------------------------------------------
Port:           1/1/22
LLDP SysName:   AP-01
LLDP SysDescr:  Alcatel-Lucent Enterprise OAW-AP1201 5.0.4.3042
LLDP PortDescr: Alcatel-Lucent Enterprise OAW-AP1201 eth0
Current alias:  'AP-01'
New alias:      'OAW-AP-01_eth0'
[y] set / [n] keep / [a] set all / [s] skip all: y
[DRY-RUN] would set: 1/1/22 → "OAW-AP-01_eth0"
--------------------------------------------------
Port:           1/1/23
LLDP SysName:   AP-02
LLDP SysDescr:  Alcatel-Lucent Enterprise OAW-AP1221 5.0.4.3042
LLDP PortDescr: Alcatel-Lucent Enterprise OAW-AP1221 eth0
Current alias:  'AP-02'
New alias:      'OAW-AP-02_eth0'
[y] set / [n] keep / [a] set all / [s] skip all: y
[DRY-RUN] would set: 1/1/23 → "OAW-AP-02_eth0"
Done.
```

### Example: apply (`a` = set this and all remaining ports)

```
SW-01> python3 ./alias-lldp.py
Reading LLDP neighbors...
Reading existing aliases...
--------------------------------------------------
Port:           1/1/22
LLDP SysName:   AP-01
LLDP SysDescr:  Alcatel-Lucent Enterprise OAW-AP1201 5.0.4.3042
LLDP PortDescr: Alcatel-Lucent Enterprise OAW-AP1201 eth0
Current alias:  'AP-01'
New alias:      'OAW-AP-01_eth0'
[y] set / [n] keep / [a] set all / [s] skip all: a
[SET] 1/1/22 → "OAW-AP-01_eth0"
--------------------------------------------------
Port:           1/1/23
LLDP SysName:   AP-02
LLDP SysDescr:  Alcatel-Lucent Enterprise OAW-AP1221 5.0.4.3042
LLDP PortDescr: Alcatel-Lucent Enterprise OAW-AP1221 eth0
Current alias:  'AP-02'
New alias:      'OAW-AP-02_eth0'
[SET] 1/1/23 → "OAW-AP-02_eth0"
Done.
```

> **Note:** Changes are applied to the running configuration only.
> Run `write memory` afterwards to make them persistent.

## Tested with

- Switch: OmniSwitch OS6360-P24, AOS 8.10.105.R02 GA
- Neighbors: OmniAccess Stellar OAW-AP1201, OAW-AP1221, OAW-AP1431 (AWOS 5.0.4)

## Disclaimer

Use at your own risk. Always test with `--dry-run` before using the script
in production.

This is not an official product and is not affiliated with or endorsed by
Alcatel-Lucent Enterprise. Alcatel-Lucent Enterprise, OmniSwitch,
OmniAccess and AOS are trademarks of their respective owners.

## License

[MIT](LICENSE) © 2026 Dominik Gawin
