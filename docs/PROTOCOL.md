# CTEK Battery Sense BLE protocol – notes

Verified on real hardware in October 2026 with two CTEK Battery Sense units,
an ESP32 (rev 3.1, ESP-IDF / Bluedroid) and ESPHome 2026.9.1.
Everything below was observed on those devices; firmware versions may differ.

## Discovery

- Advertises with the name `CTEK` (one unit advertised as `SBA`).
  Units are distinguished only by MAC address.
- Advertisements contain no measurements – a GATT connection is required.
- **Only one connection at a time.** While the CTEK app (or another gateway)
  is connected, the device stops advertising and nothing else can connect.

## Service and characteristics

Service `812ca8ed-a177-4d74-aefa-70098c5416af`

| Characteristic | Name used here | Access | Content |
|---|---|---|---|
| `a1d67c01-fe3f-01bf-7d49-7dbdc43b02a6` | unlock | write (with response) | 16-byte unlock payload |
| `a337b4eb-2544-4f94-87c9-f7732e5fe250` | samples | **notify only** (a read returns `status=2`) | 3-byte records |
| `b5634099-97c4-4f37-adf3-771246e77754` | temperature | read | 1 byte, `int8 / 2` = °C |
| `fc3119da-9b40-414e-a1c4-6c1737718cae` | cursor | read | `u16 LE` = number of records in memory |
| `e5a7e9a0-e2d7-4f46-83d1-0e55d2427780` | period | read / write | 1 byte, logging period in minutes (factory: 5) |
| `418d1817-f516-45f1-ab64-433ae596613d` | range request | write (with response) | request a block of history records |
| `337ea83e-744b-4b7c-b23f-45beaab11db7` | (clock?) | – | unknown, not needed |

## Connection sequence (order matters)

1. Connect.
2. **Unlock**: write `MD5(salt + code)` to the unlock characteristic, with response.
   - `salt` = `e1da7195eced40e4bc16559e9de73ba4` (16 bytes, from the CTEK app via upstream)
   - `code` = the 16 ASCII characters printed under the barcode on the sticker
     (upper case, no spaces). The barcode itself (Code 128) encodes the same string,
     which helps when the printed text is worn off.
   - see `tools/ctek_unlock.py`
3. **Encrypt the link**: bonding, Just Works (`ESP_LE_AUTH_REQ_SC_BOND`, `ESP_IO_CAP_NONE`,
   `esp_ble_set_encryption(..., ESP_BLE_SEC_ENCRYPT)`).
   - Encrypting **before** unlocking makes the CTEK drop the connection
     (auth fail reason 0x66, then HCI 0x13).
   - Without encryption every read fails with `status=15` (insufficient encryption).
     NimBLE stacks may secure the link automatically; ESP-IDF Bluedroid (ESPHome) does not.
4. Enable notifications on the samples characteristic (write `01 00` to its CCCD 0x2902).
5. Read temperature / cursor / period as needed.

## Samples / history records

Each record is 3 bytes:

```
byte 0-1  u16 little endian / 2048  -> battery voltage [V]
byte 2    int8 / 2                  -> temperature [°C]
```

Notifications may carry several records back to back (length multiple of 3).

The CTEK stores one record every *period* minutes in its own memory, also while
the car is driving and no gateway is in range. Records are numbered
`0 … cursor-1`. **Records carry no timestamp.** A gateway has to reconstruct the
time from the cursor: when the cursor increments, record `cursor-1` was written
"just now"; older records are `period` minutes apart.

### Range request

Write 5 bytes to `418d1817…`:

```
03  <first index u16 LE>  <count u16 LE>
```

The requested records then arrive as notifications on `a337b4eb…`, oldest first.
Requests of 18 records worked reliably.

### Logging period

- Read: 1 byte, minutes (factory default `05`).
- Write: 1 byte, 1–60. Writing `01` switches to one record per minute.
- **Writing a new period erases the stored history** – the cursor restarts at 0.
- A power cycle of the CTEK (battery disconnected) also restarts the memory.
- Memory capacity is not known yet.

## ESPHome specifics

- ESPHome logs `services released` shortly after connecting; GATT handles needed
  later (CCCD, range, period) must be captured in the first `on_connect` lambda.
- HA only receives `homeassistant.event` calls after it has subscribed. Events sent
  in the first moments after an API (re)connect are silently lost, so wait ~10 s
  after the connection appears before sending.
- The ESP must be allowed to perform Home Assistant actions
  (ESPHome integration > device > Configure).
