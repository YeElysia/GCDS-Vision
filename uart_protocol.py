'''GCDS 视觉串口协议 V2。详细格式见 SERIAL_PROTOCOL.md。'''

from maix import uart, pinmap
import struct

import vision_config as config


BAUDRATE = 115200
SOF = b'\xaa\x55'
EOF = b'\x0d\x0a'
VERSION = 0x01

# 主控 -> MaixCam
CMD_SET_TARGET = 0x10
CMD_PING = 0x11
CMD_REQUEST_STATUS = 0x12
CMD_RESET = 0x13

# MaixCam -> 主控
RSP_ACK = 0x80
EVT_DETECTION = 0x81
EVT_TASK_CODE = 0x82
EVT_STATUS = 0x83

# 检测状态
DETECT_LOST = 0x00
DETECT_FOUND = 0x01

# ACK 结果
ACK_OK = 0x00
ACK_BAD_LENGTH = 0x01
ACK_BAD_MODE = 0x02
ACK_BAD_SELECTOR = 0x03
ACK_UNSUPPORTED = 0x04


Serial_Maix0 = None
Serial_Maix1 = None


def initialize_uart():
    global Serial_Maix0, Serial_Maix1
    try:
        Serial_Maix0 = uart.UART('/dev/ttyS0', BAUDRATE)
        pinmap.set_pin_function('A18', 'UART1_RX')
        pinmap.set_pin_function('A19', 'UART1_TX')
        Serial_Maix1 = uart.UART('/dev/ttyS1', BAUDRATE)
        Serial_Maix0.set_received_callback(on_received)
        Serial_Maix1.set_received_callback(on_received)
        return True
    except Exception:
        Serial_Maix0 = None
        Serial_Maix1 = None
        return False


def crc8(data):
    '''CRC-8/ATM：poly=0x07, init=0x00, refin=false, xorout=0x00。'''
    value = 0
    for byte in data:
        value ^= byte
        for _ in range(8):
            if value & 0x80:
                value = ((value << 1) ^ 0x07) & 0xFF
            else:
                value = (value << 1) & 0xFF
    return value


def build_frame(message_type, sequence, payload=b''):
    payload = bytes(payload)
    if len(payload) > 255:
        raise ValueError('协议载荷不能超过 255 字节')
    body = bytes([
        VERSION,
        message_type & 0xFF,
        sequence & 0xFF,
        len(payload),
    ]) + payload
    return SOF + body + bytes([crc8(body)]) + EOF


_send_sequences = {}


def _next_sequence(serial):
    key = id(serial)
    sequence = (_send_sequences.get(key, 0) + 1) & 0xFF
    _send_sequences[key] = sequence
    return sequence


def send_frame(serial, message_type, payload=b'', sequence=None):
    if serial is None:
        return None
    try:
        if sequence is None:
            sequence = _next_sequence(serial)
        frame = build_frame(message_type, sequence, payload)
        serial.write(frame)
        return sequence
    except Exception:
        return None


def _clamp_int16(value):
    return max(-32768, min(32767, int(round(value))))


def _clamp_uint16(value):
    return max(0, min(65535, int(round(value))))


def _quality_byte(confidence):
    return max(0, min(100, int(round(float(confidence) * 100.0))))


def send_detection(serial, mode, target_id, target_x=0, target_y=0,
                   size=0, confidence=0.0, found=True):
    '''发送物料、圆环或码垛目标位置。

    dx = target_x - hand_x：正数表示目标在视觉中心右侧。
    dy = target_y - hand_y：正数表示目标在视觉中心下方。
    '''
    if not found or target_id == 0:
        status = DETECT_LOST
        target_id = 0
        dx = dy = cx = cy = target_size = quality = 0
    else:
        status = DETECT_FOUND
        cx = _clamp_uint16(target_x)
        cy = _clamp_uint16(target_y)
        dx = _clamp_int16(cx - config.hand_x)
        dy = _clamp_int16(cy - config.hand_y)
        target_size = _clamp_uint16(size)
        quality = _quality_byte(confidence)

    payload = struct.pack(
        '<BBBhhHHHB',
        mode & 0xFF,
        target_id & 0xFF,
        status,
        dx,
        dy,
        cx,
        cy,
        target_size,
        quality,
    )
    return send_frame(serial, EVT_DETECTION, payload)


def send_target(serial, out_x, out_y, target_id, size=0,
                confidence=1.0, mode=None):
    if mode is None:
        mode = config.Maix_State
    return send_detection(
        serial, mode, target_id, out_x, out_y, size, confidence,
        found=(target_id != 0),
    )


def send_grab(serial, out_x, out_y, color, size=0, confidence=1.0):
    return send_target(
        serial, out_x, out_y, color, size=size,
        confidence=confidence, mode=config.Maix_State,
    )


def send_task_code(serial, task_code):
    payload = str(task_code).encode('ascii')
    return send_frame(serial, EVT_TASK_CODE, payload)


def send_ack(serial, request_type, request_sequence, result, selector=0):
    payload = bytes([
        request_type & 0xFF,
        result & 0xFF,
        config.Maix_State & 0xFF,
        selector & 0xFF,
    ])
    return send_frame(serial, RSP_ACK, payload, sequence=request_sequence)


def send_status(serial, request_sequence=None):
    task_ready = 1 if config.Task_Code else 0
    payload = bytes([
        config.Maix_State & 0xFF,
        config.Color_Index & 0xFF,
        config.Position_Index & 0xFF,
        task_ready,
    ])
    return send_frame(serial, EVT_STATUS, payload, sequence=request_sequence)


def _set_target(mode, selector):
    if mode in (config.MODE_GRAB, config.MODE_STACK):
        if selector not in (1, 2, 3, 4, 5):
            return ACK_BAD_SELECTOR
        config.Maix_State = mode
        config.Color_Index = selector
        config.Position_Index = 0
        return ACK_OK
    if mode == config.MODE_RING:
        if selector not in (1, 2, 3):
            return ACK_BAD_SELECTOR
        config.Maix_State = mode
        config.Position_Index = selector
        config.Color_Index = 0
        return ACK_OK
    if mode == config.MODE_QR:
        config.Maix_State = mode
        config.Color_Index = 0
        config.Position_Index = 0
        return ACK_OK
    if mode == config.MODE_IDLE:
        config.Maix_State = mode
        config.Color_Index = 0
        config.Position_Index = 0
        return ACK_OK
    return ACK_BAD_MODE


def _handle_message(serial, message_type, sequence, payload):
    if message_type == CMD_SET_TARGET:
        if len(payload) != 2:
            send_ack(serial, message_type, sequence, ACK_BAD_LENGTH)
            return
        mode, selector = payload
        result = _set_target(mode, selector)
        send_ack(serial, message_type, sequence, result, selector)
    elif message_type == CMD_PING:
        send_ack(serial, message_type, sequence, ACK_OK)
    elif message_type == CMD_REQUEST_STATUS:
        send_status(serial, request_sequence=sequence)
    elif message_type == CMD_RESET:
        result = _set_target(config.MODE_IDLE, 0)
        send_ack(serial, message_type, sequence, result)
    else:
        send_ack(serial, message_type, sequence, ACK_UNSUPPORTED)


class FrameParser:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, serial, data):
        try:
            if not data:
                return
            self.buffer.extend(data)

            while True:
                if len(self.buffer) < 4:
                    return

                start = self.buffer.find(b'\xaa')
                if start < 0:
                    self.buffer.clear()
                    return
                if start:
                    del self.buffer[:start]
                if len(self.buffer) < 4:
                    return

                # 兼容旧版 AA mode selector BB 主控命令。
                if self.buffer[1] != 0x55:
                    if self.buffer[3] == 0xBB:
                        mode, selector = self.buffer[1], self.buffer[2]
                        del self.buffer[:4]
                        _set_target(mode, selector)
                    else:
                        del self.buffer[0]
                    continue

                if len(self.buffer) < 9:
                    return
                version = self.buffer[2]
                message_type = self.buffer[3]
                sequence = self.buffer[4]
                payload_length = self.buffer[5]
                total_length = 9 + payload_length
                if len(self.buffer) < total_length:
                    return

                payload_end = 6 + payload_length
                received_crc = self.buffer[payload_end]
                tail = bytes(self.buffer[payload_end + 1:payload_end + 3])
                crc_body = bytes(self.buffer[2:payload_end])
                payload = bytes(self.buffer[6:payload_end])

                if version != VERSION or tail != EOF or crc8(crc_body) != received_crc:
                    del self.buffer[0]
                    continue

                del self.buffer[:total_length]
                try:
                    _handle_message(serial, message_type, sequence, payload)
                except Exception:
                    continue
        except Exception:
            self.buffer.clear()


_parsers = {}


def on_received(serial, data):
    try:
        parser = _parsers.setdefault(id(serial), FrameParser())
        parser.feed(serial, data)
    except Exception:
        _parsers.pop(id(serial), None)


initialize_uart()
