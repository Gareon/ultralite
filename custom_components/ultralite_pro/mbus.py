"""M-Bus communication module for UltraLite PRO Energy Meter."""

import asyncio
import logging
import time
import struct
import datetime
from typing import Dict, Any, Optional, Tuple

import serial

_LOGGER = logging.getLogger(__name__)


def hexdump(b: bytes, width=16):
    """Debug helper to format bytes as hex dump."""
    for i in range(0, len(b), width):
        chunk = b[i:i+width]
        hexs = " ".join(f"{x:02X}" for x in chunk)
        ascii_ = "".join(chr(x) if 32 <= x <= 126 else "." for x in chunk)
        yield f"{hexs:<{width*3}} |{ascii_}|"


def mbus_checksum_ok(fr: bytes) -> bool:
    """Validate M-Bus frame checksum."""
    # Long frame: 68 L L 68 C A CI [DATA ...] CS 16
    if len(fr) < 9 or fr[0] != 0x68 or fr[3] != 0x68 or fr[-1] != 0x16:
        return False
    L = fr[1]
    if fr[2] != L:
        return False
    if len(fr) != 6 + L:  # 68 L L 68 + L bytes (C,A,CI,DATA) + CS + 16
        return False
    CS = fr[4 + L]
    return (sum(fr[4:4+L]) & 0xFF) == CS


def find_next_frame(buf: bytes):
    """Find and extract the next valid M-Bus frame from buffer."""
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
    """Little-endian packed BCD -> int (ignores 0xF nibbles)."""
    digits = []
    for x in data:
        lo, hi = x & 0x0F, (x >> 4) & 0x0F
        if lo <= 9:
            digits.append(str(lo))
        if hi <= 9:
            digits.append(str(hi))
    return int("".join(reversed(digits))) if digits else 0


def man_code_from_word(w: int) -> str:
    """Decode manufacturer code from 16-bit word."""
    c1 = ((w >> 10) & 0x1F) + 64
    c2 = ((w >> 5) & 0x1F) + 64
    c3 = (w & 0x1F) + 64
    return "".join(chr(c) if 65 <= c <= 90 else '?' for c in (c1, c2, c3))


def parse_long_frame(fr: bytes):
    """Parse M-Bus long frame to structured data."""
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
        if i >= len(recs_bytes):
            break
        DIF = recs_bytes[i]
        i += 1
        if DIF in (0x0F, 0x1F, 0x2F):  # special/fill
            recs.append({"ofs": start, "special": hex(DIF)})
            continue
        
        # DIFE chain
        difes = []
        while (DIF & 0x80) and i < len(recs_bytes):
            d = recs_bytes[i]
            i += 1
            difes.append(d)
            if not (d & 0x80):
                break
        if i >= len(recs_bytes):
            break
            
        # VIF + VIFE(s)
        VIF = recs_bytes[i]
        i += 1
        vifes = []
        while (VIF & 0x80) and i < len(recs_bytes):
            v = recs_bytes[i]
            i += 1
            vifes.append(v)
            if not (v & 0x80):
                break

        # Data length/type (DIF low nibble)
        dl = DIF & 0x0F
        raw, value = b"", None
        if dl in (0x1, 0x2, 0x3, 0x4, 0x6, 0x7):  # unsigned ints 8/16/24/32/48/64
            size = {1: 1, 2: 2, 3: 3, 4: 4, 6: 6, 7: 8}[dl]
            if i + size <= len(recs_bytes):
                raw = recs_bytes[i:i+size]
                i += size
                value = int.from_bytes(raw, "little")
        elif dl == 0x5:  # 32-bit float
            if i + 4 <= len(recs_bytes):
                raw = recs_bytes[i:i+4]
                i += 4
                value = struct.unpack("<f", raw)[0]
        elif dl in (0x9, 0xA, 0xB, 0xC, 0xE):  # BCD 2/4/6/8/12-digit
            size = {0x9: 1, 0xA: 2, 0xB: 3, 0xC: 4, 0xE: 6}[dl]
            if i + size <= len(recs_bytes):
                raw = recs_bytes[i:i+size]
                i += size
                value = decode_bcd_le(raw)
        elif dl == 0xD:  # variable-length (LVAR)
            if i < len(recs_bytes):
                LVAR = recs_bytes[i]
                i += 1
                if i + LVAR <= len(recs_bytes):
                    raw = recs_bytes[i:i+LVAR]
                    i += LVAR
                    value = raw  # keep bytes
        
        recs.append({
            "ofs": start, "DIF": DIF, "VIF": VIF, "DIFEs": difes, "VIFEs": vifes,
            "raw": raw, "value": value
        })
    
    return {"ctrl": C, "addr": A, "ci": CI, "fixed": fixed, "records": recs}


def _ts(secs):
    """Convert timestamp to ISO format."""
    try:
        return datetime.datetime.fromtimestamp(int(secs), datetime.timezone.utc).isoformat()
    except Exception:
        return None


def _volume_scaled(vif, val_int):
    """Volume family 0x20..0x27: m³ * 10^(n-6) where n=vif&7."""
    n = vif & 0x07
    return float(val_int) * (10 ** (n - 6))


# VIF mapping for UltraLite PRO meter
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
}

# VIF=0xFD (extension) → map by first VIFE (masked to 7-bit)
VIF_EXT_MAP = {
    0x0E: ("firmware_version", lambda v: int(v), None),
    0x0F: ("software_version", lambda v: int(v), None),
    0x08: ("access_number",    lambda v: int(v), None),
    0x09: ("medium_code",      lambda v: int(v), None),
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

    return None


def short_frame(ctrl, addr):
    """Create M-Bus short frame."""
    return bytes([0x10, ctrl, addr, (ctrl + addr) & 0xFF, 0x16])


class MBusReader:
    """M-Bus reader for UltraLite PRO meter."""
    
    def __init__(self, usb_path: str, primary_address: int = 0xFE):
        """Initialize M-Bus reader."""
        self.usb_path = usb_path
        self.primary_address = primary_address
        self._serial: Optional[serial.Serial] = None
        
    async def connect(self) -> bool:
        """Connect to the USB device."""
        try:
            self._serial = serial.Serial(
                self.usb_path,
                baudrate=2400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.15
            )
            _LOGGER.debug("Connected to %s", self.usb_path)
            return True
        except (serial.SerialException, OSError) as e:
            _LOGGER.error("Failed to connect to %s: %s", self.usb_path, e)
            self._serial = None
            return False
    
    def disconnect(self):
        """Disconnect from the USB device."""
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._serial = None
    
    async def _send_wakeup_8n1(self) -> None:
        """Send wakeup sequence at 2400 8N1."""
        if not self._serial:
            raise serial.SerialException("Not connected")
            
        self._serial.baudrate = 2400
        self._serial.bytesize = serial.EIGHTBITS
        self._serial.parity = serial.PARITY_NONE
        self._serial.stopbits = serial.STOPBITS_ONE
        self._serial.timeout = 0
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()
        
        chunk = b"\x55" * 32
        t0 = time.time()
        while time.time() - t0 < 2.2:
            await asyncio.get_event_loop().run_in_executor(None, self._serial.write, chunk)
        
        await asyncio.get_event_loop().run_in_executor(None, self._serial.flush)
        await asyncio.sleep(0.05)
    
    async def _send_cmds_8e1(self) -> None:
        """Send M-Bus commands at 2400 8E1."""
        if not self._serial:
            raise serial.SerialException("Not connected")
            
        self._serial.parity = serial.PARITY_EVEN
        self._serial.timeout = 0
        self._serial.reset_input_buffer()
        
        snd_nke = short_frame(0x40, self.primary_address)
        req_ud2 = short_frame(0x7B, self.primary_address)
        
        await asyncio.get_event_loop().run_in_executor(None, self._serial.write, snd_nke)
        await asyncio.get_event_loop().run_in_executor(None, self._serial.flush)
        await asyncio.sleep(0.35)
        
        await asyncio.get_event_loop().run_in_executor(None, self._serial.write, req_ud2)
        await asyncio.get_event_loop().run_in_executor(None, self._serial.flush)
    
    async def _read_window(self, window_s: float) -> bytes:
        """Read data from serial port within time window."""
        if not self._serial:
            raise serial.SerialException("Not connected")
            
        deadline = time.time() + window_s
        buf = bytearray()
        self._serial.timeout = 0.15
        
        while time.time() < deadline:
            part = await asyncio.get_event_loop().run_in_executor(None, self._serial.read, 512)
            if part:
                buf.extend(part)
        
        return bytes(buf)
    
    async def read_data(self) -> Dict[str, Any]:
        """Read data from the meter."""
        if not self._serial or not self._serial.is_open:
            if not await self.connect():
                raise serial.SerialException("Cannot connect to device")
        
        try:
            # Send wakeup and commands
            await self._send_wakeup_8n1()
            await asyncio.sleep(0.35)
            await self._send_cmds_8e1()
            
            # Read response
            buf = await self._read_window(2.5)
            
            # Parse frames
            values = {}
            work = buf
            while True:
                fr, work = find_next_frame(work)
                if not fr:
                    break
                if fr[0] == 0x68 and mbus_checksum_ok(fr):
                    parsed = parse_long_frame(fr)
                    
                    # Extract device info
                    fixed = parsed.get("fixed", {})
                    if fixed:
                        values["device_id"] = fixed.get("id")
                        values["manufacturer"] = fixed.get("manufacturer")
                        values["version"] = fixed.get("version")
                        values["medium"] = fixed.get("medium")
                        values["access_no"] = fixed.get("access_no")
                        values["status"] = fixed.get("status")
                    
                    # Map known records
                    for r in parsed["records"]:
                        m = record_to_human(r)
                        if m:
                            k, v, u = m
                            values[k] = {"value": v, "unit": u}
            
            # Calculate thermal power if we have flow and delta_T
            if ("volume_flow" in values and "delta_temperature" in values and
                values["volume_flow"]["value"] is not None and 
                values["delta_temperature"]["value"] is not None):
                flow_m3h = float(values["volume_flow"]["value"])
                dT = float(values["delta_temperature"]["value"])
                power_kW = 1.163 * flow_m3h * dT
                values["thermal_power"] = {"value": power_kW, "unit": "kW"}
            
            if not values:
                raise ValueError("No valid data received from meter")
                
            _LOGGER.debug("Successfully read data: %s", values)
            return values
            
        except Exception as e:
            _LOGGER.error("Error reading data: %s", e)
            self.disconnect()
            raise
