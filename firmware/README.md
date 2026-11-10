# Light sensor (optional)

An ESP32-C3 Super Mini with a GY-302 (BH1750) light sensor, running ESPHome. It answers lux over Wi-Fi:

    GET http://lux-sensor.local/sensor/Illuminance  ->  {"id":"sensor/Illuminance","value":29.2,"state":"29.2 lx"}

Then add the sensor to Yarilo's settings, `%USERPROFILE%\.yarilo\config.json`:

    "sensor_urls": ["http://lux-sensor.local/sensor/Illuminance"]

Some browsers and programs do not resolve `.local` names. You can add the IP address as a second URL,
and give the board a fixed address in your router.

## Parts

- ESP32-C3 Super Mini.
- GY-302 module (BH1750).
- Four thin wires, 28–30 AWG.
- A USB-C cable that carries data.

## Wiring

| Wire | Super Mini | GY-302 |
|---|---|---|
| power | 3.3 | VCC |
| ground | G | GND |
| clock | GPIO1 | SCL |
| data | GPIO0 | SDA |
| — | — | ADDR: leave free, the address is then 0x23 |

The GY-302 already has its I²C pull-up resistors. GPIO0 and GPIO1 are used because GPIO2, 8 and 9 are
strapping pins on the ESP32-C3 (GPIO8 is also the LED), and GPIO20/21 are the UART.

Keep the sensor out of the monitors' light: it should see the room, not the screen. A printable wall
case for these two boards is in [`hardware/case/`](../hardware/case/).

## Flashing

1. Install ESPHome into its own environment: `py -m venv .venv`, then `.venv\Scripts\pip install esphome`.
2. Copy `secrets.example.yaml` to `secrets.yaml` and fill it in. The Wi-Fi network must be 2.4 GHz.
   `secrets.yaml` is git-ignored.
3. In **PowerShell or cmd**, not Git Bash, run `esphome run lux-sensor.yaml` from this folder. ESP-IDF
   refuses to install under MSYS. The first build downloads the toolchain, several hundred MB.
4. The first flash goes over USB: choose the board's COM port. Later updates can go over Wi-Fi.

A new board with empty flash reboots every few seconds, and its COM port keeps appearing and
disappearing. This is normal. If flashing cannot catch the port, unplug the board, hold BOOT and plug
it in again.

The board's page with live values is `http://lux-sensor.local/`.
