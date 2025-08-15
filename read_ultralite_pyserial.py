#!/usr/bin/env python3
# read_ultralite_pyserial.py
#
# Requires: pip install pyserial
# What it does:
#  - 2400 baud 8N1: send 0x55 for ~2.2 s (wake-up)
#  - switch to 2400 8E1: send SND_NKE (reset) then REQ_UD2 (class-2 data)
#  - read + validate M-Bus long frame, parse header + records, print
#  - keep retrying in a loop so you can adjust the IR probe position

import sys, time, struct
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"

# ---------- low-level M-Bus helpers ----------

def mbus_checksum_ok(frame: bytes) -> bool:
    # Long frame: 68 L L 68 C A CI [DATA..] CS 16 ; CS=sum(C..last DATA)&0xFF
    if len(frame) < 9 or frame[0] != 0x68 or frame[3] != 0x68 or frame[-1] != 0x16:
        return False
    L = frame[1]
    if L != frame[2] or len(frame) != 6 + L:
        return False
    calc = sum(frame[4:4+L-1]) & 0xFF
    return calc == frame[4+L-1]

def find_next_frame(buf: bytes):
    """Return (frame, remaining) for ACK/short/long frame, or (None, buf)."""
    i, n = 0, len(buf)
    while i < n:
        b = buf[i]
        # ACK
        if b == 0xE5:
            return buf[i:i+1], buf[i+1:]
        # Short: 10 C A CS 16
        if b == 0x10 and i + 5 <= n:
            fr = buf[i:i+5]
            if fr[-1] == 0x16 and ((fr[1] + fr[2]) & 0xFF) == fr[3]:
                return fr, buf[i+5:]
        # Long: 68 L L 68 ... 16
        if b == 0x68 and i + 6 <= n:
            L = buf[i+1]
            if i + 6 + L <= n and buf[i+2] == L and buf[i+3] == 0x68:
                fr = buf[i:i+6+L]
                if fr[-1] == 0x16 and mbus_checksum_ok(fr):
                    return fr, buf[i+6+L:]
        i += 1
    return None, buf

def decode_bcd_le(data: bytes) -> int:
    """Little-endian packed BCD -> int (ignores 0xF nibbles)."""
    digits = []
    for b in data:
        lo, hi = b & 0x0F, (b >> 4) & 0x0F
        if lo <= 9: digits.append(str(lo))
        if hi <= 9: digits.append(str(hi))
    return int("".join(reversed(digits))) if digits else 0

def man_code_from_word(w: int) -> str:
    # 3*5-bit letters packed; A=1 -> ord('A')=65
    c1 = ((w >> 10) & 0x1F) + 64
    c2 = ((w >> 5) & 0x1F) + 64
    c3 = (w & 0x1F) + 64
    return "".join(chr(c) if 65 <= c <= 90 else '?' for c in (c1, c2, c3))

def parse_long_frame(frame: bytes):
    # assumes checksum OK
    L = frame[1]
    C, A, CI = frame[4], frame[5], frame[6]
    data = frame[7:7+(L-4)]  # minus C,A,CI,CS

    fixed = {}
    recs_bytes = data
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

    # Generic records: DIF[/DIFE...] VIF[/VIFE...] DATA
    recs = []
    i = 0
    while i < len(recs_bytes):
        start = i
        DIF = recs_bytes[i]; i += 1
        if DIF in (0x0F, 0x1F, 0x2F):  # special/fill
            recs.append({"ofs": start, "special_dif": hex(DIF)})
            continue
        difes = []
        while (DIF & 0x80) and i < len(recs_bytes):
            d = recs_bytes[i]; i += 1
            difes.append(d)
            if not (d & 0x80):
                break
        if i >= len(recs_bytes): break
        VIF = recs_bytes[i]; i += 1
        vifes = []
        while (VIF & 0x80) and i < len(recs_bytes):
            v = recs_bytes[i]; i += 1
            vifes.append(v)
            if not (v & 0x80):
                break

        dl = DIF & 0x0F
        raw, value = b"", None
        if dl == 0x0:
            pass
        elif dl in (0x1,0x2,0x3,0x4,0x6,0x7):  # unsigned int
            size = {1:1,2:2,3:3,4:4,6:6,7:8}[dl]
            if i + size <= len(recs_bytes):
                raw = recs_bytes[i:i+size]; i += size
                value = int.from_bytes(raw, "little")
        elif dl == 0x5:  # 32-bit float
            if i + 4 <= len(recs_bytes):
                raw = recs_bytes[i:i+4]; i += 4
                value = struct.unpack("<f", raw)[0]
        elif dl in (0x9,0xA,0xB,0xC,0xE):  # BCD
            size = {0x9:1,0xA:2,0xB:3,0xC:4,0xE:6}[dl]
            if i + size <= len(recs_bytes):
                raw = recs_bytes[i:i+size]; i += size
                value = decode_bcd_le(raw)
        elif dl == 0xD:  # variable length (LVAR)
            if i < len(recs_bytes):
                LVAR = recs_bytes[i]; i += 1
                if i + LVAR <= len(recs_bytes):
                    raw = recs_bytes[i:i+LVAR]; i += LVAR
                    value = raw  # keep bytes
        else:
            # unknown; avoid getting stuck
            break

        recs.append({
            "ofs": start,
            "DIF": hex(DIF), "DIFEs": [hex(d) for d in difes],
            "VIF": hex(VIF), "VIFEs": [hex(v) for v in vifes],
            "raw": raw.hex(),
            "value": value,
        })
    return {"ctrl": C, "addr": A, "ci": CI, "fixed": fixed, "records": recs}

# ---------- serial I/O ----------

def send_wakeup_8N1(ser):
    ser.baudrate = 2400
    ser.bytesize = serial.EIGHTBITS
    ser.parity   = serial.PARITY_NONE
    ser.stopbits = serial.STOPBITS_ONE
    ser.timeout  = 0  # non-blocking
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    # ~2.2 s of 0x55 @ 2400 baud (~530 bytes). Send in chunks.
    chunk = b"\x55" * 32
    t0 = time.time()
    while time.time() - t0 < 2.2:
        ser.write(chunk)
    ser.flush()
    time.sleep(0.05)

def send_cmds_8E1(ser):
    ser.parity = serial.PARITY_EVEN
    ser.timeout = 0
    ser.reset_input_buffer()
    # SND_NKE to address 0x00: 10 40 00 40 16
    ser.write(bytes([0x10, 0x40, 0x00, 0x40, 0x16]))
    ser.flush()
    time.sleep(0.35)
    # REQ_UD2 to broadcast 0xFE: 10 7B FE 79 16
    ser.write(bytes([0x10, 0x7B, 0xFE, 0x79, 0x16]))
    ser.flush()

def read_one_response(ser, window_s=2.0):
    deadline = time.time() + window_s
    buf = bytearray()
    ser.timeout = 0.1  # small chunked reads
    while time.time() < deadline:
        part = ser.read(512)
        if part:
            buf.extend(part)
            fr, rem = find_next_frame(buf)
            if fr:
                # Prefer long RSP_UD (C=0x08/0x18), but print whatever long frame we got
                if fr[0] == 0x68 and mbus_checksum_ok(fr):
                    return fr
                # ignore ACK/short; keep waiting for long data
                buf[:] = rem
    return None

def pretty_print(parsed):
    print("— M-Bus RSP_UD —")
    print(f"  Ctrl=0x{parsed['ctrl']:02X}  Addr={parsed['addr']}  CI=0x{parsed['ci']:02X}")
    if parsed["fixed"]:
        f = parsed["fixed"]
        print(f"  ID={f['id']}  Man={f['manufacturer']}  Ver={f['version']}  Med=0x{f['medium']:02X}")
        print(f"  AccessNo={f['access_no']}  Status=0x{f['status']:02X}  Sig=0x{f['signature']:04X}")
    print("  Records:")
    for r in parsed["records"]:
        if "special_dif" in r:
            print(f"    @+{r['ofs']:03d}: special {r['special_dif']}")
            continue
        val = r["value"]
        if isinstance(val, bytes):
            val = val.hex()
        print(f"    @+{r['ofs']:03d}: DIF={r['DIF']} VIF={r['VIF']} "
              f"DIFEs={r['DIFEs']} VIFEs={r['VIFEs']} raw={r['raw']} value={val}")
    print()

def main():
    print(f"Opening {PORT} @ 2400 baud (IR M-Bus)...")
    with serial.Serial(PORT, baudrate=2400, bytesize=serial.EIGHTBITS,
                       parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE) as ser:
        try:
            while True:
                send_wakeup_8N1(ser)
                time.sleep(0.35)
                send_cmds_8E1(ser)
                fr = read_one_response(ser, window_s=2.0)
                if fr:
                    parsed = parse_long_frame(fr) if fr[0] == 0x68 and mbus_checksum_ok(fr) else None
                    if parsed:
                        pretty_print(parsed)
                    else:
                        print("Received non-long frame:", fr.hex())
                else:
                    # show progress heartbeat while you move the head for best alignment
                    print(".", end="", flush=True)
                time.sleep(0.4)
        except KeyboardInterrupt:
            print("\nBye.")

if __name__ == "__main__":
    main()
