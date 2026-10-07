# Vitrea Scenarios for Home Assistant

Minimal custom integration that runs scenarios on a Vitrea V-Box over its local TCP protocol (v2). Nothing else — no lights, switches or covers.

## Install (HACS)

1. HACS -> Integrations -> three-dot menu -> Custom repositories
2. Add this repository URL, category = Integration
3. Install "Vitrea Scenarios", restart Home Assistant
4. Settings -> Devices & Services -> Add Integration -> "Vitrea Scenarios"
5. Enter V-Box host, port (default `11501`), username and password

## Manual install

Copy `custom_components/vitrea_scenarios/` into your Home Assistant `config/custom_components/` directory and restart.

## Usage

The integration adds one action, `vitrea_scenarios.run_scenario`:

```yaml
action: vitrea_scenarios.run_scenario
data:
  scenario_id: 10
```

Use it from scripts, automations, or dashboard buttons.

## Notes

- The V-Box seems to accept only one TCP client at a time. The integration opens a short-lived connection per call (connect, login, run, disconnect) so it doesn't lock out the Vitrea app — but a call will fail while another client is connected.
- Wire format: `56 54 55 3e 34 00 04 <msg_id> <scenario_id> 03 <checksum>`. The meaning of the trailing `0x03` is unknown; it's what the official app sends.

## Credits

Datagram framing and login are based on the JavaScript [`vitrea-client`](https://github.com/bdsoha/vitrea-client) library by [@bdsoha](https://github.com/bdsoha). The scenario command was reverse-engineered from a packet capture.
