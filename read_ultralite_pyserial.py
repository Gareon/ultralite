#!/usr/bin/env python3
# read_ultralite_human.py — Itron/Integral-V style M-Bus readout with human-readable values
# - wakeup 0x55 @ 2400 8N1, then SND_NKE + REQ_UD2 @ 2400 8E1
# - parses long frame and maps the common VIFs we see on these meters
# - loops forever so you can tune the IR head (Ctrl-C to stop)

import sys, time, struct, argparse, datetime
import serial

def hexdump(b: bytes, width=16):
    for i in range(0, len(b), width):
        chunk = b[i:i+width]
        hexs = " ".join(f"{x:02X}" for x in chunk)
        ascii_ = "".join(chr(x) if 32 <= x <= 126 else "." for x in chunk)
        yield f"{hexs:<{width*3}} |{ascii_}|"

# ---------- M-Bus framing (L excludes CS) ----------
def mbus_checksum_ok(fr: bytes) -> bool:
    if len(fr) < 9 or fr[0] != 0x68 or fr[3] != 0x68 or fr[-1] != 0x16:
        return False
    L = fr[1]
    if fr[2] != L: return False
    if len(fr) != 6 + L:  # 68 L L 68 + L (C,A,CI,DATA) + CS + 16
        return False
    CS = fr[4 + L]
    return (sum(fr[4:4+L]) & 0xFF) == CS

def find_next_frame(buf: bytes):
    i, n = 0, len(buf)
    while i < n:
        b = buf[i]
        if b == 0xE5:  # ACK
            return buf[i:i+1], buf[i+1:]
        if b == 0x10 and i + 5 <= n:  # short
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

# ---------- little helpers ----------
def decode_bcd_le(data: bytes) -> int:
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

# ---------- parse long frame ----------
def parse_long_frame(fr: bytes):
    L = fr[1]
    C, A, CI = fr[4], fr[5], fr[6]
    data = fr[7:7+(L-3)]  # remove C,A,CI (3 bytes); L excludes CS
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
        if DIF in (0x0F, 0x1F, 0x2F):
            recs.append({"ofs": start, "special": hex(DIF)})
            continue
        difes = []
        while (DIF & 0x80) and i < len(recs_bytes):
            d = recs_bytes[i]; i += 1
            difes.append(d)
            if not (d & 0x80): break
        if i >= len(recs_bytes): break
        VIF = recs_bytes[i]; i += 1
        vifes = []
        while (VIF & 0x80) and i < len(recs_bytes):
            v = recs_bytes[i]; i += 1
            vifes.append(v)
            if not (v & 0x80): break

        dl = DIF & 0x0F
        raw, value = b"", None
        if dl in (0x1,0x2,0x3,0x4,0x6,0x7):
            size = {1:1,2:2,3:3,4:4,6:6,7:8}[dl]
            if i + size <= len(recs_bytes):
                raw = recs_bytes[i:i+size]; i += size
                value = int.from_bytes(raw, "little")
        elif dl == 0x5:
            if i + 4 <= len(recs_bytes):
                raw = recs_bytes[i:i+4]; i += 4
                value = struct.unpack("<f", raw)[0]
        elif dl in (0x9,0xA,0xB,0xC,0xE):
            size = {0x9:1,0xA:2,0xB:3,0xC:4,0xE:6}[dl]
            if i + size <= len(recs_bytes):
                raw = recs_bytes[i:i+size]; i += size
                value = decode_bcd_le(raw)
        elif dl == 0xD:
            if i < len(recs_bytes):
                LVAR = recs_bytes[i]; i += 1
                if i + LVAR <= len(recs_bytes):
                    raw = recs_bytes[i:i+LVAR]; i += LVAR
                    value = raw
        recs.append({
            "ofs": start,
            "DIF": DIF, "VIF": VIF,
            "DIFEs": difes, "VIFEs": vifes,
            "raw": raw, "value": value,
        })
    return {"ctrl": C, "addr": A, "ci": CI, "fixed": fixed, "records": recs}

# ---------- VIF → human mapper (just the ones we saw) ----------
def as_human(r):
    VIF = r["VIF"]; VIFEs = r["VIFEs"]; val = r["value"]; raw = r["raw"]
    name, unit, shown = None, None, None

    # Serial / fabrication number (0x78, 8-digit BCD)
    if VIF == 0x78 and isinstance(val, int):
        return ("serial_number", str(val), "")

    # Energy (1 kWh) — VIF 0x06 (per EN 13757-3 + vendor docs)
    if VIF == 0x06 and isinstance(val, int):
        return ("energy_total", float(val), "kWh")

    # Energy in joules 10^n — 0x10..0x17 (we only saw 0x14)
    if 0x10 <= VIF <= 0x17 and isinstance(val, int):
        n = VIF & 0x07  # nnn
        joule = float(val) * (10 ** n)
        return ("energy_total_J", joule, "J")

    # Volume (10^(n-6) m³): 0x20..0x27 (e.g. 0x27 = 10 m³ units)
    if 0x20 <= VIF <= 0x27 and isinstance(val, int):
        n = VIF & 0x07
        m3 = float(val) * (10 ** (n - 6))
        return ("volume_total", m3, "m³")

    # Volume flow (10^(n-6) m³/h): 0x38..0x3F (e.g. 0x3B = 1 L/h)
    if 0x38 <= VIF <= 0x3F and isinstance(val, int):
        n = VIF & 0x07
        m3h = float(val) * (10 ** (n - 6))
        # also provide L/h if small
        return ("volume_flow", m3h, "m³/h")

    # Flow / Return temperature (°C), step 10^(nn-3): 0x58..0x5B / 0x5C..0x5F
    if 0x58 <= VIF <= 0x5B and isinstance(val, int):
        nn = VIF & 0x03
        return ("flow_temperature", float(val) * (10 ** (nn - 3)), "°C")
    if 0x5C <= VIF <= 0x5F and isinstance(val, int):
        nn = VIF & 0x03
        return ("return_temperature", float(val) * (10 ** (nn - 3)), "°C")

    # Temperature difference (K): 0x60..0x63 (we saw 0x61 -> 0.01 K)
    if 0x60 <= VIF <= 0x63 and isinstance(val, int):
        nn = VIF & 0x03
        return ("delta_temperature", float(val) * (10 ** (nn - 3)), "K")

    # Time point (date/time) Type F — 0x6D (many meters use Unix epoch seconds)
    if VIF == 0x6D and isinstance(val, int):
        try:
            dt = datetime.datetime.utcfromtimestamp(val).isoformat() + "Z"
            return ("timestamp", dt, "")
        except Exception:
            return ("timestamp_raw", val, "")

    # Extensions with VIF = 0xFD (linear extension) — a few handy ones
    if VIF == 0xFD and VIFEs:
        ext = VIFEs[0] & 0x7F  # first VIFE without ext-bit
        if ext == 0x0E and isinstance(val, int):
            return ("firmware_version", int(val), "")
        if ext == 0x0F and isinstance(val, int):
            return ("software_version", int(val), "")
        if ext == 0x08 and isinstance(val, int):
            return ("access_number", int(val), "")
        if ext == 0x09 and isinstance(val, int):
            return ("medium_code", int(val), "")
        if ext == 0x0A and isinstance(val, int):
            return ("manufacturer_code", int(val), "")

    return None  # unknown/leave generic

# ---------- serial I/O + loop ----------
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

def print_human(parsed, also_dump_generic=False):
    f = parsed.get("fixed", {})
    if f:
        print(f"Meter: ID={f['id']}  Man={f['manufacturer']}  Ver={f['version']}  Medium=0x{f['medium']:02X}  AccessNo={f['access_no']}  Status=0x{f['status']:02X}")
    # Collect mapped values
    mapped = []
    for r in parsed["records"]:
        if "special" in r: continue
        m = as_human(r)
        if m:
            mapped.append(m)
    # De-duplicate by key (keep last)
    out = {}
    for k, v, u in mapped:
        out[k] = (v, u)
    # Pretty print
    print("Values:")
    for k in sorted(out.keys()):
        v, u = out[k]
        if isinstance(v, float) and (u in ("kWh","m³","m³/h","°C","K")):
            print(f"  {k}: {v:.3f} {u}".rstrip())
        else:
            print(f"  {k}: {v} {u}".rstrip())
    # Optional: generic fallback lines for unknowns
    if also_dump_generic:
        print("\n(Decoded records, raw):")
        for r in parsed["records"]:
            if "special" in r:
                print(f"  @+{r['ofs']:03d}: special {hex(r['DIF'])}"); continue
            raw_hex = r['raw'].hex() if isinstance(r['raw'], (bytes,bytearray)) else (r['raw'] or b"").hex()
            val = r['value']
            if isinstance(val, bytes): val = val.hex()
            print(f"  @+{r['ofs']:03d}: DIF=0x{r['DIF']:x} VIF=0x{r['VIF']:x} VIFEs={[hex(x) for x in r['VIFEs']]} value={val} raw={raw_hex}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", default="/dev/ttyUSB0")
    ap.add_argument("--addr", default="0xFE")
    ap.add_argument("--window", type=float, default=2.5)
    ap.add_argument("--cycle", type=float, default=0.5)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--save")
    ap.add_argument("--sniff", action="store_true")
    ap.add_argument("--show-generic", action="store_true")
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
                work = buf
                any_frame = False
                while True:
                    fr, work = find_next_frame(work)
                    if not fr: break
                    if fr[0] == 0x68 and mbus_checksum_ok(fr):
                        any_frame = True
                        parsed = parse_long_frame(fr)
                        print_human(parsed, also_dump_generic=args.show_generic)
                if not any_frame:
                    print(".", end="", flush=True)
                time.sleep(args.cycle)
        except KeyboardInterrupt:
            print("\nBye.")
        finally:
            if save_fh: save_fh.close()

if __name__ == "__main__":
    main()
