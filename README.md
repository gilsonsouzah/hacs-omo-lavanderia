# Omo Lavanderia Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/gsouza/omo-lavanderia.svg)](https://github.com/gsouza/omo-lavanderia/releases)
[![License](https://img.shields.io/github/license/gsouza/omo-lavanderia.svg)](LICENSE)

A Home Assistant custom integration for monitoring and controlling washing machines at Omo Lavanderia (Machine Guardian API).

## Features

- 🧺 **Real-time machine monitoring** - Track the status of all washing machines in your laundry
- ⏱️ **Cycle progress tracking** - See remaining time for running cycles
- 💳 **Card balance monitoring** - Check your laundry card balance
- 🚀 **Remote start** - Start available machines directly from Home Assistant
- 🔔 **Automation ready** - Create notifications for cycle completion, low balance, etc.
- 🗣️ **Voice assistant compatible** - Works with Alexa, Google Home, and Siri

## Installation

### HACS (Recommended)

1. Make sure you have [HACS](https://hacs.xyz/) installed
2. Go to HACS → Integrations → ⋮ (top right menu) → Custom repositories
3. Add `https://github.com/gsouza/omo-lavanderia` as a custom repository (Category: Integration)
4. Click "Install"
5. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/gsouza/omo-lavanderia/releases)
2. Extract the `omo_lavanderia` folder to your `custom_components` directory
3. Restart Home Assistant

```
custom_components/
└── omo_lavanderia/
    ├── __init__.py
    ├── manifest.json
    ├── config_flow.py
    ├── const.py
    ├── coordinator.py
    ├── entity.py
    ├── sensor.py
    ├── binary_sensor.py
    ├── button.py
    ├── services.yaml
    ├── strings.json
    ├── api/
    │   ├── __init__.py
    │   ├── auth.py
    │   ├── client.py
    │   ├── exceptions.py
    │   └── models.py
    └── translations/
        ├── en.json
        └── pt-BR.json
```

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Omo Lavanderia"
4. Enter your credentials:
   - **Username**: Your Omo Lavanderia app email
   - **Password**: Your Omo Lavanderia app password
5. Select your laundry location and card
6. Click **Submit**

## Entities

### Sensors

| Entity                               | Description                                                 |
| ------------------------------------ | ----------------------------------------------------------- |
| `sensor.omo_lavanderia_card_balance` | Current balance on your laundry card (R$)                   |
| `sensor.machine_X_status`            | Status of machine X (Available, In Use, Out of Order, etc.) |
| `sensor.machine_X_remaining_time`    | Remaining time for the current cycle (minutes)              |
| `sensor.machine_X_cycle_end_time`    | Estimated end time of the current cycle                     |
| `sensor.machine_X_price`             | Price per cycle for machine X                               |

### Binary Sensors

| Entity                                   | Description                                        |
| ---------------------------------------- | -------------------------------------------------- |
| `binary_sensor.machine_X_available`      | Whether machine X is available for use             |
| `binary_sensor.machine_X_running`        | Whether machine X is currently running a cycle     |
| `binary_sensor.machine_X_occupied_by_me` | Whether you started the current cycle on machine X |

### Buttons

| Entity                   | Description                                 |
| ------------------------ | ------------------------------------------- |
| `button.machine_X_start` | Start a cycle on machine X (when available) |

## Services

### `omo_lavanderia.start_cycle`

Start a washing cycle on a specific machine.

| Parameter    | Required | Description                                      |
| ------------ | -------- | ------------------------------------------------ |
| `machine_id` | Yes      | The ID of the machine to start                   |
| `card_id`    | No       | The card ID to use (defaults to configured card) |

**Example:**

```yaml
service: omo_lavanderia.start_cycle
data:
  machine_id: 'ABC123'
```

## Automation Examples

### Notify When Cycle is About to End

Get notified 5 minutes before your washing cycle ends:

```yaml
automation:
  - alias: 'Notify Laundry Almost Done'
    trigger:
      - platform: numeric_state
        entity_id: sensor.machine_1_remaining_time
        below: 5
        above: 0
    condition:
      - condition: state
        entity_id: binary_sensor.machine_1_occupied_by_me
        state: 'on'
    action:
      - service: notify.mobile_app
        data:
          title: '🧺 Lavanderia'
          message: "Sua roupa estará pronta em {{ states('sensor.machine_1_remaining_time') }} minutos!"
          data:
            push:
              sound: default
```

### Notify When Cycle Completes

```yaml
automation:
  - alias: 'Notify Laundry Complete'
    trigger:
      - platform: state
        entity_id: binary_sensor.machine_1_running
        from: 'on'
        to: 'off'
    condition:
      - condition: state
        entity_id: binary_sensor.machine_1_occupied_by_me
        state: 'on'
    action:
      - service: notify.mobile_app
        data:
          title: '✅ Lavanderia'
          message: 'Sua roupa está pronta! Vá buscar na máquina 1.'
          data:
            push:
              sound: default
              interruption-level: time-sensitive
```

### Low Balance Alert

```yaml
automation:
  - alias: 'Low Laundry Card Balance'
    trigger:
      - platform: numeric_state
        entity_id: sensor.omo_lavanderia_card_balance
        below: 20
    action:
      - service: notify.mobile_app
        data:
          title: '💳 Saldo Baixo'
          message: "Seu cartão da lavanderia tem apenas R$ {{ states('sensor.omo_lavanderia_card_balance') }}. Considere recarregar!"
```

### Dashboard Card Example

```yaml
type: entities
title: Lavanderia
entities:
  - entity: sensor.omo_lavanderia_card_balance
    name: Saldo do Cartão
  - type: divider
  - entity: sensor.machine_1_status
    name: Máquina 1
  - entity: sensor.machine_1_remaining_time
    name: Tempo Restante
  - entity: button.machine_1_start
    name: Iniciar Máquina 1
  - type: divider
  - entity: sensor.machine_2_status
    name: Máquina 2
  - entity: sensor.machine_2_remaining_time
    name: Tempo Restante
```

## Alexa Integration

To use with Alexa, expose your entities through the [Home Assistant Cloud](https://www.nabucasa.com/) or [Alexa Smart Home Skill](https://www.home-assistant.io/integrations/alexa/).

### Recommended Alexa Routines

1. **"Alexa, como está a lavanderia?"**
   - Create a routine that reads the status of available machines and your card balance

2. **"Alexa, avise quando a roupa estiver pronta"**
   - Trigger an Alexa announcement when `binary_sensor.machine_X_running` changes to off

### Example Alexa Routine (via Home Assistant)

```yaml
automation:
  - alias: 'Alexa Announce Laundry Done'
    trigger:
      - platform: state
        entity_id: binary_sensor.machine_1_running
        from: 'on'
        to: 'off'
    action:
      - service: notify.alexa_media
        data:
          target: media_player.echo_sala
          message: 'Sua roupa está pronta na lavanderia!'
          data:
            type: announce
```

## Google Home Integration

Expose sensors to Google Home for voice queries:

- "Hey Google, what's my laundry card balance?"
- "Hey Google, is the washing machine available?"

## Troubleshooting

### Authentication Issues

If you encounter authentication errors:

1. Verify your credentials in the Omo Lavanderia app
2. Remove the integration and re-add it
3. Check the Home Assistant logs for detailed error messages

### Machines Not Updating

The integration polls the API every 60 seconds. If machines aren't updating:

1. Check your internet connection
2. Verify the API is accessible
3. Check Home Assistant logs for errors

### Debug Logging

Enable debug logging by adding to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.omo_lavanderia: debug
```

## Contributing

Contributions are welcome! Please read our [contributing guidelines](CONTRIBUTING.md) before submitting a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or connected to Omo, Unilever, or Machine Guardian. Use at your own risk.

## Support

- 🐛 [Report a bug](https://github.com/gsouza/omo-lavanderia/issues/new?template=bug_report.md)
- 💡 [Request a feature](https://github.com/gsouza/omo-lavanderia/issues/new?template=feature_request.md)
- 💬 [Discussions](https://github.com/gsouza/omo-lavanderia/discussions)
