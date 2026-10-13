'''智能搬运视觉主入口。'''
from maix import camera, display, gpio, touchscreen, app

import vision_config as config
import lab_color_detector as lab_detect
import ring_detector
from qr_task_reader import QRTaskReader
import uart_protocol as uart_proto
import touch_ui as ui


try:
    cam = camera.Camera(320, 240, fps=60)
except Exception:
    cam = None
try:
    disp = display.Display()
except Exception:
    disp = None
try:
    ts = touchscreen.TouchScreen()
except Exception:
    ts = None
try:
    img = cam.read() if cam is not None else None
except Exception:
    img = None

try:
    led = gpio.GPIO("B3", gpio.Mode.OUT)
    led.value(1)
except Exception:
    led = None

if img is not None and disp is not None:
    try:
        ui.init_buttons(img, disp)
    except Exception:
        pass
qr_reader = QRTaskReader()
previous_state = config.Maix_State
ring_frame_counter = 0


def handle_buttons():
    px, py, pressed = ts.read()

    if ui.CC_btn.click(img, px, py, pressed):
        config.Maix_State = config.MODE_GRAB
    if ui.EE_btn.click(img, px, py, pressed):
        config.Maix_State = config.MODE_RING
    if ui.ST_btn.click(img, px, py, pressed):
        config.Maix_State = config.MODE_STACK
    if ui.QR_btn.click(img, px, py, pressed):
        config.Maix_State = config.MODE_QR
    if ui.FF_btn.click(img, px, py, pressed):
        config.Maix_State = config.MODE_IDLE
    if config.Maix_State in (config.MODE_GRAB, config.MODE_STACK):
        if ui.R_btn.click(img, px, py, pressed): config.Color_Index = 1
        if ui.Y_btn.click(img, px, py, pressed): config.Color_Index = 2
        if ui.B_btn.click(img, px, py, pressed): config.Color_Index = 3
        if ui.G_btn.click(img, px, py, pressed): config.Color_Index = 4
        if ui.LB_btn.click(img, px, py, pressed): config.Color_Index = 5
    elif config.Maix_State == config.MODE_RING:
        if ui.P1_btn.click(img, px, py, pressed): config.Position_Index = 1
        if ui.P2_btn.click(img, px, py, pressed): config.Position_Index = 2
        if ui.P3_btn.click(img, px, py, pressed): config.Position_Index = 3

    if config.Maix_State == config.MODE_GRAB:
        _handle_CC_buttons(px, py, pressed)
    elif config.Maix_State == config.MODE_IDLE:
        _handle_FF_buttons(px, py, pressed)


def _handle_CC_buttons(px, py, pressed):
    if 1 <= config.Color_Index <= 5:
        th = config.LAB_runtime[config.Color_Index]
        if ui.prev_btn.click(img, px, py, pressed):
            config.param_idx = (config.param_idx - 1) % 6
        if ui.next_btn.click(img, px, py, pressed):
            config.param_idx = (config.param_idx + 1) % 6

        pmax = 127 if config.param_idx >= 2 else 100
        pmin = -128 if config.param_idx >= 2 else 0
        if config.Color_Index == 5 and config.param_idx == 3:
            pmax = config.LIGHT_BLUE_MAX_A
        if config.Color_Index == 4 and config.param_idx == 3:
            pmax = config.GREEN_MAX_A
        if config.Color_Index == 5 and config.param_idx == 2:
            pmin = config.LIGHT_BLUE_MIN_A
        if config.Color_Index == 5 and config.param_idx == 4:
            pmin = config.LIGHT_BLUE_MIN_B
        if config.Color_Index == 5 and config.param_idx == 5:
            pmax = config.LIGHT_BLUE_MAX_B
        if ui.m10_btn.click(img, px, py, pressed):
            th[config.param_idx] = max(th[config.param_idx] - 10, pmin)
        if ui.m1_btn.click(img, px, py, pressed):
            th[config.param_idx] = max(th[config.param_idx] - 1, pmin)
        if ui.p1_btn.click(img, px, py, pressed):
            th[config.param_idx] = min(th[config.param_idx] + 1, pmax)
        if ui.p10_btn.click(img, px, py, pressed):
            th[config.param_idx] = min(th[config.param_idx] + 10, pmax)

    if ui.save_btn.click(img, px, py, pressed):
        config._save_lab()
    if ui.reset_btn.click(img, px, py, pressed):
        config._reset_lab()
        config.param_idx = 0


def _handle_FF_buttons(px, py, pressed):
    if ui.fxp_btn.click(img, px, py, pressed): config.ERROR_x += 1
    if ui.fxm_btn.click(img, px, py, pressed): config.ERROR_x -= 1
    if ui.fyp_btn.click(img, px, py, pressed): config.ERROR_y += 1
    if ui.fym_btn.click(img, px, py, pressed): config.ERROR_y -= 1
    if ui.fsv_btn.click(img, px, py, pressed):
        config.change_file('/root/error.txt', 1, f'x={config.ERROR_x}')
        config.change_file('/root/error.txt', 2, f'y={config.ERROR_y}')
    if ui.fzr_btn.click(img, px, py, pressed):
        config.ERROR_x = 0
        config.ERROR_y = 0
        config.change_file('/root/error.txt', 1, 'x=0')
        config.change_file('/root/error.txt', 2, 'y=0')
    config.update_hand_xy()


def _safe_send(method, serial, *args, **kwargs):
    if serial is None:
        return
    try:
        method(serial, *args, **kwargs)
    except Exception:
        pass


def _send_lost():
    mode = config.Maix_State
    if mode in (config.MODE_GRAB, config.MODE_STACK):
        for serial in (uart_proto.Serial_Maix0, uart_proto.Serial_Maix1):
            _safe_send(uart_proto.send_grab, serial, 0, 0, 0)
    elif mode == config.MODE_RING:
        for serial in (uart_proto.Serial_Maix0, uart_proto.Serial_Maix1):
            _safe_send(uart_proto.send_target, serial, 0, 0, 0,
                       mode=config.MODE_RING)


def _safe_read_frame():
    if cam is None:
        return None
    try:
        return cam.read()
    except Exception:
        return None


def _safe_handle_buttons():
    if ts is None:
        return
    try:
        handle_buttons()
    except Exception:
        pass


def _safe_draw_ui(frame):
    try:
        ui.draw_UI(frame)
    except Exception:
        pass


def _safe_show(frame):
    if disp is None:
        return
    try:
        disp.show(frame)
    except Exception:
        pass


def _safe_reset_target():
    config.Target = [0, 0, 0, 0, 0]


def _process_frame(frame):
    global previous_state, ring_frame_counter, img
    img = frame
    try:
        if config.Maix_State != previous_state:
            if previous_state == config.MODE_RING or config.Maix_State == config.MODE_RING:
                ring_detector.reset_tracker()
                ring_frame_counter = 0
                _safe_reset_target()
            if config.Maix_State in (config.MODE_GRAB, config.MODE_STACK):
                lab_detect.reset_trackers()
            if config.Maix_State == config.MODE_QR:
                qr_reader.reset()
            previous_state = config.Maix_State
    except Exception:
        _safe_reset_target()

    try:
        if led is not None:
            led.value(1)
    except Exception:
        pass

    mode = config.Maix_State
    try:
        if mode in (config.MODE_GRAB, config.MODE_STACK):
            color_index = config.Color_Index
            if color_index in lab_detect.adapts:
                config.Target = lab_detect.find_color(frame, color_index)
                lab_detect.adapts[color_index].alter(config.Target[3] != 0)
            else:
                _safe_reset_target()

            target = config.Target
            if target[3] != 0:
                try:
                    frame.draw_circle(int(target[0]), int(target[1]), int(target[2]),
                                      config.draw_color[target[3]], thickness=2)
                except Exception:
                    pass
                confidence = min(1.0, float(target[4]) / 2000.0)
                for serial in (uart_proto.Serial_Maix0, uart_proto.Serial_Maix1):
                    _safe_send(uart_proto.send_grab, serial, target[0], target[1],
                               target[3], size=target[2], confidence=confidence)
            else:
                _send_lost()

        elif mode == config.MODE_RING:
            if config.Position_Index:
                ring_frame_counter += 1
                if (ring_frame_counter > config.RING_WARMUP_FRAMES and
                        ring_frame_counter % config.RING_DETECT_INTERVAL == 0):
                    config.Target = ring_detector.find_ring(frame, config.Position_Index)
            else:
                _safe_reset_target()

            target = config.Target
            if target[3] != 0:
                try:
                    frame.draw_circle(int(target[0]), int(target[1]), int(target[2]),
                                      config.CYAN, thickness=2)
                    frame.draw_cross(int(target[0]), int(target[1]), config.WHITE,
                                     size=8, thickness=2)
                except Exception:
                    pass
                for serial in (uart_proto.Serial_Maix0, uart_proto.Serial_Maix1):
                    _safe_send(uart_proto.send_target, serial, target[0], target[1],
                               target[3], size=target[2], confidence=target[4],
                               mode=config.MODE_RING)
            else:
                _send_lost()

        elif mode == config.MODE_QR:
            plan, rect, is_new = qr_reader.update(frame)
            if rect is not None:
                try:
                    frame.draw_rect(rect[0], rect[1], rect[2], rect[3], config.CYAN, 2)
                except Exception:
                    pass
            if plan is not None:
                config.Task_Plan = plan
                config.Task_Code = plan['raw']
            if is_new:
                for serial in (uart_proto.Serial_Maix0, uart_proto.Serial_Maix1):
                    _safe_send(uart_proto.send_task_code, serial, config.Task_Code)

        elif mode == config.MODE_IDLE:
            _safe_reset_target()
            config.Color_Index = 0
            config.Position_Index = 0
    except Exception:
        _safe_reset_target()
        _send_lost()

    _safe_handle_buttons()
    _safe_draw_ui(frame)
    _safe_show(frame)


while not app.need_exit():
    frame = _safe_read_frame()
    if frame is None:
        _send_lost()
        continue
    try:
        _process_frame(frame)
    except Exception:
        _safe_reset_target()
        _send_lost()
