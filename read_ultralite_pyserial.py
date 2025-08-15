#!/usr/bin/env python3
# read_ultralite_vifmap.py
# PySerial M-Bus reader for Itron / Integral-V UltraLite PRO (IR head on /dev/ttyUSBx)
# - Wakeup: 0x55 @ 2400 8N1
# - Request: SND_NKE + REQ_UD2 @ 2400 8E1
# - Parses long frames and prints human-readable values using VIF_MAP
#
# Notes for this meter profile (based on your captures):
#   * VIF 0x06  -> cumulative energy in kWh (unsigned)
#   * VIF 0x14  -> cumulative volume with 0.01 m³ resolution (BCD)
#   * VIF 0x38..0x3F -> volume flow, scale 10^(n-6) m³/h (n=VIF&7). For 0x3B: /1000.
#   * VIF 0x5A -> flow temp (°C, 0.1 steps); 0x5E -> return temp (°C, 0.1 steps)
#   * VIF 0x61 -> ΔT (K, 0.01 steps)
#   * VIF 0x6D -> time point (epoch seconds -> ISO-8601, vendor-profile)
#   * VIF 0x78 -> serial/fabrication number (BCD, 8 digits)
#   * VIF 0x27 -> interpreted here as operating time (days) per field use seen (16-bit int)
#   * VIF 0xFD + VIFE 0x0E/0x0F -> firmware/software versions (uint8)
#
# Derivations:
#   * thermal_power_kW = 1.163 * volume_flow(m³/h) * delta_temperature(K)

import sys, time, argparse, datetime, struct
import serial

# ------------ Debug helpers ------------
def hexdump(b: bytes, width=16):
    for i in range(0, len(b), width):
        chunk = b[i:i+width]
        hexs = " ".join(f"{x:02X}" for x in chunk)
        ascii_ = "".join(chr(x) if 32 <= x <= 126 else "." for x in chunk)
        yield f"{hexs:<{width*3}} |{ascii_}|"

# ------------ M-Bus framing (L excludes CS) ------------
def mbus_checksum_ok(fr: bytes) -> bool:
    # Long frame: 68 L L 68 C A CI [DATA ...] CS 16
    if len(fr) < 9 or fr[0] != 0x68 or fr[3] != 0x68 or fr[-1] != 0x16:
        return False
    L = fr[1]
    if fr[2] != L: return False
    if len(fr) != 6 + L:  # 68 L L 68 + L bytes (C,A,CI,DATA) + CS + 16
        return False
    CS = fr[4 + L]
    return (sum(fr[4:4+L]) & 0xFF) == CS

def find_next_frame(buf: bytes):
    i, n = 0, len(buf)
    while i < n:
        b = buf[i]
        if b == 0xE5:  # ACK
            return buf[i:i+1], buf[i+1:]
        if b == 0x10 and i + 5 <= n:  # short: 10 C A CS 16
            fr = buf[i:i+5]
            if fr[-1] == 0x16 and ((fr[1] + fr[2]) & 0xFF) == fr[3]:
                return fr, buf[i+5:]
        if b == 0x68 and i + 6 <= n:
            L = buf[i+1]
            if i + 6 + L <= n and buf[i+2] == L and buf[i+3] == 0x68:
                fr = buf[i:i+6+L]
                if fr[-1] == 0x16 and mbus_checksum_ok(fr):
                    return fr, buf[i+6+L:]
        i += 1
    return None, buf

# ------------ Basic decoders ------------
def decode_bcd_le(data: bytes) -> int:
    """Little-endian packed BCD -> int (ignores 0xF nibbles)."""
    digits = []
    for x in data:
        lo, hi = x & 0x0F, (x >> 4) & 0x0F
        if lo <= 9: digits.append(str(lo))
        if hi <= 9: digits.append(str(hi))
    return int("".join(reversed(digits))) if digits else 0

def man_code_from_word(w: int) -> str:
    c1 = ((w >> 10) & 0x1F) + 64
    c2 = ((w >> 5) & 0x1F) + 64
    c3 = (w & 0x1F) + 64
    return "".join(chr(c) if 65 <= c <= 90 else '?' for c in (c1, c2, c3))

# ------------ Parse long frame to generic records ------------
def parse_long_frame(fr: bytes):
    L = fr[1]
    C, A, CI = fr[4], fr[5], fr[6]
    data = fr[7:7 + (L - 3)]  # strip C,A,CI (3 bytes), L excludes CS
    fixed, recs_bytes = {}, data
    if len(data) >= 12:
        fixed = {
            "id": decode_bcd_le(data[0:4]),
            "manufacturer": man_code_from_word(int.from_bytes(data[4:6], "little")),
            "version": data[6],
            "medium": data[7],
            "access_no": data[8],
            "status": data[9],
            "signature": int.from_bytes(data[10:12], "little"),
        }
        recs_bytes = data[12:]

    recs = []
    i = 0
    while i < len(recs_bytes):
        start = i
        if i >= len(recs_bytes): break
        DIF = recs_bytes[i]; i += 1
        if DIF in (0x0F, 0x1F, 0x2F):  # special/fill
            recs.append({"ofs": start, "special": hex(DIF)})
            continue
        # DIFE chain
        difes = []
        while (DIF & 0x80) and i < len(recs_bytes):
            d = recs_bytes[i]; i += 1
            difes.append(d)
            if not (d & 0x80): break
        if i >= len(recs_bytes): break
        # VIF + VIFE(s)
        VIF = recs_bytes[i]; i += 1
        vifes = []
        while (VIF & 0x80) and i < len(recs_bytes):
            v = recs_bytes[i]; i += 1
            vifes.append(v)
            if not (v & 0x80): break

        # Data length/type (DIF low nibble)
        dl = DIF & 0x0F
        raw, value = b"", None
        if dl in (0x1,0x2,0x3,0x4,0x6,0x7):  # unsigned ints 8/16/24/32/48/64
            size = {1:1,2:2,3:3,4:4,6:6,7:8}[dl]
            if i + size <= len(recs_bytes):
                raw = recs_bytes[i:i+size]; i += size
                value = int.from_bytes(raw, "little")
        elif dl == 0x5:  # 32-bit float
            if i + 4 <= len(recs_bytes):
                raw = recs_bytes[i:i+4]; i += 4
                value = struct.unpack("<f", raw)[0]
        elif dl in (0x9,0xA,0xB,0xC,0xE):  # BCD 2/4/6/8/12-digit
            size = {0x9:1,0xA:2,0xB:3,0xC:4,0xE:6}[dl]
            if i + size <= len(recs_bytes):
                raw = recs_bytes[i:i+size]; i += size
                value = decode_bcd_le(raw)
        elif dl == 0xD:  # variable-length (LVAR)
            if i < len(recs_bytes):
                LVAR = recs_bytes[i]; i += 1
                if i + LVAR <= len(recs_bytes):
                    raw = recs_bytes[i:i+LVAR]; i += LVAR
                    value = raw  # keep bytes
        recs.append({"ofs": start, "DIF": DIF, "VIF": VIF, "DIFEs": difes, "VIFEs": vifes,
                     "raw": raw, "value": value})
    return {"ctrl": C, "addr": A, "ci": CI, "fixed": fixed, "records": recs}

# ------------ VIF → human mapping ------------
def _ts(secs):
    try:
        return datetime.datetime.utcfromtimestamp(int(secs)).isoformat() + "Z"
    except Exception:
        return None

def _volume_scaled(vif, val_int):
    """Volume family 0x20..0x27: m³ * 10^(n-6) where n=vif&7."""
    n = vif & 0x07
    return float(val_int) * (10 ** (n - 6))

VIF_MAP = {
    0x06: ("energy_total",        lambda v, vif: float(v),          "kWh"),
    0x14: ("volume_total",        lambda v, vif: float(v) / 100.0,  "m³"),    # 0.01 m³ (BCD)
    0x27: ("operating_time_days", lambda v, vif: int(v),            "days"),  # seen in your frames
    0x38: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
    0x39: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
    0x3A: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
    0x3B: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
    0x3C: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
    0x3D: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
    0x3E: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
    0x3F: ("volume_flow",         lambda v, vif: _volume_scaled(vif, v), "m³/h"),
    0x5A: ("flow_temperature",    lambda v, vif: float(v) / 10.0,   "°C"),
    0x5E: ("return_temperature",  lambda v, vif: float(v) / 10.0,   "°C"),
    0x61: ("delta_temperature",   lambda v, vif: float(v) / 100.0,  "K"),
    0x6D: ("time_point",          lambda v, vif: _ts(v),            None),
    0x78: ("serial_number",       lambda v, vif: str(int(v)).zfill(8), None),
    # You can add more VIFs here if the meter exposes them.
}

# VIF=0xFD (extension) → map by first VIFE (masked to 7-bit)
VIF_EXT_MAP = {
    0x0E: ("firmware_version", lambda v: int(v), None),
    0x0F: ("software_version", lambda v: int(v), None),
    0x08: ("access_number",    lambda v: int(v), None),
    0x09: ("medium_code",      lambda v: int(v), None),
    # extend as needed
}

def record_to_human(r):
    """Return (key, value, unit) or None if not mapped."""
    if "special" in r or r["value"] is None:
        return None
    VIF = r["VIF"]
    val = r["value"]

    # Extension VIF (0xFD)
    if VIF == 0xFD and r["VIFEs"]:
        vife = r["VIFEs"][0] & 0x7F  # first non-ext VIFE
        if vife in VIF_EXT_MAP:
            name, fn, unit = VIF_EXT_MAP[vife]
            return (name, fn(val), unit)
        return None

    # Direct map
    if VIF in VIF_MAP:
        name, fn, unit = VIF_MAP[VIF]
        try:
            return (name, fn(val, VIF), unit)
        except TypeError:
            # backward compat if lambda v (no vif arg)
            return (name, fn(val), unit)

    # Generic volume family 0x20..0x27 if you want to surface others:
    if 0x20 <= VIF <= 0x27 and isinstance(val, int):
        return ("volume_scaled", _volume_scaled(VIF, val), "m³")

    return None

# ------------ Serial + loop ------------
def short_frame(ctrl, addr):
    return bytes([0x10, ctrl, addr, (ctrl + addr) & 0xFF, 0x16])

def send_wakeup_8N1(ser, debug=False):
    ser.baudrate = 2400
    ser.bytesize = serial.EIGHTBITS
    ser.parity   = serial.PARITY_NONE
    ser.stopbits = serial.STOPBITS_ONE
    ser.timeout  = 0
    ser.reset_input_buffer(); ser.reset_output_buffer()
    chunk = b"\x55" * 32
    t0 = time.time()
    while time.time() - t0 < 2.2:
        ser.write(chunk)
    ser.flush()
    if debug: print("[TX] wakeup 0x55 x ~2.2s")
    time.sleep(0.05)

def send_cmds_8E1(ser, addr, debug=False):
    ser.parity = serial.PARITY_EVEN
    ser.timeout = 0
    ser.reset_input_buffer()
    snd_nke = short_frame(0x40, addr)
    req_ud2 = short_frame(0x7B, addr)
    ser.write(snd_nke); ser.flush()
    if debug: print(f"[TX] SND_NKE -> 0x{addr:02X}: {snd_nke.hex(' ')}")
    time.sleep(0.35)
    ser.write(req_ud2); ser.flush()
    if debug: print(f"[TX] REQ_UD2 -> 0x{addr:02X}: {req_ud2.hex(' ')}")

def read_window(ser, window_s, debug=False, save_fh=None):
    deadline = time.time() + window_s
    buf = bytearray()
    ser.timeout = 0.15
    while time.time() < deadline:
        part = ser.read(512)
        if part:
            if save_fh: save_fh.write(part); save_fh.flush()
            buf.extend(part)
            if debug:
                ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[RX {ts}] {len(part)} bytes")
                for line in hexdump(part): print("   ", line)
    return bytes(buf)

def print_human(parsed, show_generic=False, compute_power=True):
    f = parsed.get("fixed", {})
    if f:
        print(f"Meter: ID={f['id']}  Man={f['manufacturer']}  Ver={f['version']}  "
              f"Medium=0x{f['medium']:02X}  AccessNo={f['access_no']}  Status=0x{f['status']:02X}")

    # Map known records
    values = {}
    for r in parsed["records"]:
        m = record_to_human(r)
        if m:
            k, v, u = m
            values[k] = (v, u)  # keep last occurrence

    # Derived: thermal power (kW) if we have flow & delta_T
    if compute_power and ("volume_flow" in values) and ("delta_temperature" in values):
        flow_m3h = float(values["volume_flow"][0])
        dT = float(values["delta_temperature"][0])
        power_kW = 1.163 * flow_m3h * dT
        values["thermal_power"] = (power_kW, "kW")

    # Pretty print
    print("Values:")
    preferred_order = [
        "serial_number",
        "energy_total",
        "volume_total",
        "volume_flow",
        "flow_temperature",
        "return_temperature",
        "delta_temperature",
        "thermal_power",
        "operating_time_days",
        "firmware_version",
        "software_version",
        "timestamp",
    ]
    for k in preferred_order:
        if k in values:
            v, u = values[k]
            unit = (u or "").strip()
            if isinstance(v, float) and u in ("kWh","m³","m³/h","°C","K","kW"):
                print(f"  {k}: {v:.3f}{(' ' + unit) if unit else ''}".rstrip())
            else:
                print(f"  {k}: {v}{(' ' + unit) if unit else ''}".rstrip())

    # Optional: generic fallback for unmapped records
    if show_generic:
        print("\n(Decoded records, raw):")
        for r in parsed["records"]:
            if "special" in r:
                print(f"  @+{r['ofs']:03d}: special {r['special']}")
                continue
            val = r["value"]
            if isinstance(val, bytes): val = val.hex()
            raw_hex = r["raw"].hex() if isinstance(r["raw"], (bytes, bytearray)) else ""
            difes = [hex(x) for x in r["DIFEs"]]
            vifes = [hex(x) for x in r["VIFEs"]]
            print(f"  @+{r['ofs']:03d}: DIF=0x{r['DIF']:x} VIF=0x{r['VIF']:x} DIFEs={difes} VIFEs={vifes} value={val} raw={raw_hex}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", default="/dev/ttyUSB0")
    ap.add_argument("--addr", default="0xFE", help="primary address (e.g., 0xFE, 0x00)")
    ap.add_argument("--window", type=float, default=2.5, help="read window per cycle (s)")
    ap.add_argument("--cycle", type=float, default=0.5, help="pause between cycles (s)")
    ap.add_argument("--debug", action="store_true", help="print raw RX hexdumps")
    ap.add_argument("--save", help="save raw RX bytes to file")
    ap.add_argument("--sniff", action="store_true", help="listen only (no requests), 2400 8E1")
    ap.add_argument("--show-generic", action="store_true", help="also print generic undecoded records")
    args = ap.parse_args()

    addr = int(args.addr, 0)
    save_fh = open(args.save, "ab") if args.save else None

    print(f"Opening {args.port} @ 2400 baud...")
    with serial.Serial(args.port, baudrate=2400, bytesize=serial.EIGHTBITS,
                       parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE) as ser:
        try:
            while True:
                if not args.sniff:
                    send_wakeup_8N1(ser, debug=args.debug)
                    time.sleep(0.35)
                    send_cmds_8E1(ser, addr, debug=args.debug)
                else:
                    ser.baudrate = 2400
                    ser.bytesize = serial.EIGHTBITS
                    ser.parity   = serial.PARITY_EVEN
                    ser.stopbits = serial.STOPBITS_ONE
                    ser.timeout  = 0.15

                buf = read_window(ser, args.window, debug=args.debug, save_fh=save_fh)
                any_frame = False
                work = buf
                while True:
                    fr, work = find_next_frame(work)
                    if not fr: break
                    if fr[0] == 0x68 and mbus_checksum_ok(fr):
                        any_frame = True
                        parsed = parse_long_frame(fr)
                        print_human(parsed, show_generic=args.show_generic)
                if not any_frame:
                    print(".", end="", flush=True)
                time.sleep(args.cycle)
        except KeyboardInterrupt:
            print("\nBye.")
        finally:
            if save_fh: save_fh.close()

if __name__ == "__main__":
    main()
