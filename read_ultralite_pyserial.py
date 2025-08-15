#!/usr/bin/env python3
# read_ultralite_dump.py
# PySerial + hexdump debugging for Integral-V UltraLite PRO (M-Bus via IR head)
# - Wake: 2400 8N1, send 0x55 ~2.2s
# - Request: 2400 8E1, SND_NKE + REQ_UD2 (addr configurable)
# - Dump: print every received chunk (if --debug), save to file (if --save),
#         and try to parse M-Bus frames. Loops forever.

import sys, time, struct, argparse, binascii, datetime
import serial

def hexdump(b: bytes, width=16):
    for i in range(0, len(b), width):
        chunk = b[i:i+width]
        hexs = " ".join(f"{x:02X}" for x in chunk)
        ascii_ = "".join(chr(x) if 32 <= x <= 126 else "." for x in chunk)
        yield f"{hexs:<{width*3}} |{ascii_}|"

def mbus_checksum_ok(fr: bytes) -> bool:
    if len(fr) < 9 or fr[0] != 0x68 or fr[3] != 0x68 or fr[-1] != 0x16:
        return False
    L = fr[1]
    if L != fr[2] or len(fr) != 6 + L:  # 68 L L 68 [L bytes incl CS] 16
        return False
    return (sum(fr[4:4+L-1]) & 0xFF) == fr[4+L-1]

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

def parse_long_frame(fr: bytes):
    L = fr[1]
    C, A, CI = fr[4], fr[5], fr[6]
    data = fr[7:7+(L-4)]  # minus C,A,CI,CS
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
        recs.append({"ofs": start, "DIF": hex(DIF), "DIFEs":[hex(x) for x in difes],
                     "VIF": hex(VIF), "VIFEs":[hex(x) for x in vifes],
                     "raw": raw.hex(), "value": value})
    return {"ctrl": C, "addr": A, "ci": CI, "fixed": fixed, "records": recs}

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
    if debug:
        print("[TX] wakeup 0x55 x ~2.2s")
    time.sleep(0.05)

def short_frame(ctrl, addr):
    # 10 C A CS 16  ; CS=(C+A)&0xFF
    cs = (ctrl + addr) & 0xFF
    return bytes([0x10, ctrl, addr, cs, 0x16])

def send_cmds_8E1(ser, addr, debug=False):
    ser.parity = serial.PARITY_EVEN
    ser.timeout = 0
    ser.reset_input_buffer()
    snd_nke = short_frame(0x40, addr)
    req_ud2 = short_frame(0x7B, addr)  # request class 2 data
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
            if save_fh:
                save_fh.write(part); save_fh.flush()
            buf.extend(part)
            if debug:
                ts = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
                print(f"[RX {ts}] {len(part)} bytes")
                for line in hexdump(part):
                    print("   ", line)
    return bytes(buf)

def print_frames_from(buf):
    # Try to peel off every valid frame and print a summary
    work = buf
    any_frame = False
    while True:
        fr, work = find_next_frame(work)
        if not fr: break
        any_frame = True
        if len(fr) == 1 and fr[0] == 0xE5:
            print("[FRAME] ACK E5")
            continue
        if fr[0] == 0x10 and len(fr) == 5:
            print(f"[FRAME] SHORT: {fr.hex(' ')}")
            continue
        if fr[0] == 0x68:
            ok = mbus_checksum_ok(fr)
            print(f"[FRAME] LONG ({'OK' if ok else 'BAD-CS'}), {len(fr)} bytes")
            print("        ", fr.hex(" "))
            if ok:
                p = parse_long_frame(fr)
                f = p.get("fixed", {})
                if f:
                    print(f"        ID={f['id']} Man={f['manufacturer']} Ver={f['version']} "
                          f"Med=0x{f['medium']:02X} Acc={f['access_no']} Sta=0x{f['status']:02X}")
                print("        Records:")
                for r in p["records"]:
                    if "special" in r:
                        print(f"          @+{r['ofs']:03d}: special {r['special']}")
                        continue
                    val = r['value']
                    if isinstance(val, bytes): val = val.hex()
                    print(f"          @+{r['ofs']:03d}: DIF={r['DIF']} VIF={r['VIF']} "
                          f"DIFEs={r['DIFEs']} VIFEs={r['VIFEs']} raw={r['raw']} value={val}")
    return any_frame

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", default="/dev/ttyUSB0")
    ap.add_argument("--addr", default="0xFE", help="primary address (e.g. 0xFE, 0x00, 0x01)")
    ap.add_argument("--window", type=float, default=2.5, help="read window per cycle (s)")
    ap.add_argument("--cycle", type=float, default=0.5, help="pause between cycles (s)")
    ap.add_argument("--debug", action="store_true", help="print raw RX hexdumps")
    ap.add_argument("--save", help="save all raw RX bytes to file")
    ap.add_argument("--sniff", action="store_true", help="just listen (no requests), 2400 8E1")
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
                    # switch to 8E1 & send to selected address
                    send_cmds_8E1(ser, addr, debug=args.debug)
                else:
                    # sniff mode: just set 8E1 and listen
                    ser.baudrate = 2400
                    ser.bytesize = serial.EIGHTBITS
                    ser.parity   = serial.PARITY_EVEN
                    ser.stopbits = serial.STOPBITS_ONE
                    ser.timeout  = 0.15

                buf = read_window(ser, args.window, debug=args.debug, save_fh=save_fh)
                if buf:
                    got = print_frames_from(buf)
                    if not got and not args.debug:
                        # show something so you know bytes arrived but no valid frame detected
                        print(f"[RX] {len(buf)} bytes (no valid M-Bus frame found)")
                else:
                    print(".", end="", flush=True)
                time.sleep(args.cycle)
        except KeyboardInterrupt:
            print("\nBye.")
        finally:
            if save_fh: save_fh.close()

if __name__ == "__main__":
    main()
