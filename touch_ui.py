'''MaixCam 触摸屏按钮和视觉调参界面。'''
from maix import image, time

import vision_config as config


class Button:
    def __init__(self, x, y, w, h, label, img, disp, fill=None, text_c=None):
        self.size = image.string_size(label)
        self.x, self.y, self.w, self.h = x, y, w, h
        x2 = x + self.size.width() + 2 * w
        y2 = y + self.size.height() + 2 * h
        self.position = [x, y, x2, y2]
        self.label = label
        self.fill = fill
        self.text_c = text_c
        self.disp_pos = image.resize_map_pos(
            img.width(), img.height(), disp.width(), disp.height(),
            image.Fit.FIT_CONTAIN, x, y, x2, y2,
        )
        self.last_x = self.last_y = 0
        self.last_pressed = False
        self.pressed_already = False

    def draw(self, img, highlight=False):
        x, y = self.position[0], self.position[1]
        width = self.position[2] - self.position[0]
        height = self.position[3] - self.position[1]
        img.draw_rect(x, y, width, height, self.fill or config.WHITE, -1)
        img.draw_rect(x, y, width, height,
                      config.WHITE if highlight else config.DGRAY,
                      3 if highlight else 2)
        img.draw_string(self.x + self.w, self.y + self.h, self.label,
                        self.text_c or config.BLACK, scale=1, thickness=1)

    def click(self, img, px, py, pressed):
        if px != self.last_x or py != self.last_y or pressed != self.last_pressed:
            self.last_x, self.last_y = px, py
            self.last_pressed = pressed
        if pressed:
            self.pressed_already = True
        elif self.pressed_already:
            self.pressed_already = False
            if (self.disp_pos[0] < px < self.disp_pos[2] and
                    self.disp_pos[1] < py < self.disp_pos[3]):
                return True
        return False


LED_btn = CC_btn = EE_btn = ST_btn = QR_btn = FF_btn = None
R_btn = Y_btn = B_btn = G_btn = LB_btn = None
P1_btn = P2_btn = P3_btn = None
prev_btn = next_btn = None
m10_btn = m1_btn = p1_btn = p10_btn = None
save_btn = reset_btn = None
fxp_btn = fxm_btn = fyp_btn = fym_btn = fsv_btn = fzr_btn = None
color_btns = []


def init_buttons(img, disp):
    global LED_btn, CC_btn, EE_btn, ST_btn, QR_btn, FF_btn
    global R_btn, Y_btn, B_btn, G_btn, LB_btn, color_btns
    global P1_btn, P2_btn, P3_btn
    global prev_btn, next_btn, m10_btn, m1_btn, p1_btn, p10_btn
    global save_btn, reset_btn
    global fxp_btn, fxm_btn, fyp_btn, fym_btn, fsv_btn, fzr_btn

    LED_btn = Button(2, 2, 3, 8, 'L', img, disp, fill=config.GRAY, text_c=config.WHITE)
    CC_btn = Button(35, 2, 4, 8, 'CC', img, disp)
    EE_btn = Button(77, 2, 4, 8, 'EE', img, disp)
    ST_btn = Button(119, 2, 4, 8, 'ST', img, disp)
    QR_btn = Button(161, 2, 4, 8, 'QR', img, disp)
    FF_btn = Button(203, 2, 4, 8, 'FF', img, disp)

    R_btn = Button(2, 27, 10, 5, 'R', img, disp, fill=config.RED, text_c=config.WHITE)
    Y_btn = Button(2, 69, 10, 5, 'Y', img, disp, fill=config.YELLOW, text_c=config.BLACK)
    B_btn = Button(2, 111, 10, 5, 'DB', img, disp, fill=config.BLUE, text_c=config.WHITE)
    G_btn = Button(2, 153, 10, 5, 'G', img, disp, fill=config.GREEN, text_c=config.BLACK)
    LB_btn = Button(2, 195, 10, 5, 'LB', img, disp, fill=config.LIGHT_BLUE, text_c=config.BLACK)
    color_btns = [R_btn, Y_btn, B_btn, G_btn, LB_btn]

    P1_btn = Button(2, 45, 14, 12, '1', img, disp, fill=config.LGRAY)
    P2_btn = Button(2, 100, 14, 12, '2', img, disp, fill=config.LGRAY)
    P3_btn = Button(2, 155, 14, 12, '3', img, disp, fill=config.LGRAY)

    prev_btn = Button(45, 28, 4, 6, '<', img, disp, fill=config.LGRAY)
    next_btn = Button(185, 28, 4, 6, '>', img, disp, fill=config.LGRAY)
    m10_btn = Button(45, 56, 3, 6, '-10', img, disp, fill=config.LGRAY)
    m1_btn = Button(95, 56, 3, 6, '-1', img, disp, fill=config.LGRAY)
    p1_btn = Button(145, 56, 3, 6, '+1', img, disp, fill=config.LGRAY)
    p10_btn = Button(195, 56, 3, 6, '+10', img, disp, fill=config.LGRAY)
    save_btn = Button(45, 208, 4, 8, 'Save', img, disp, fill=config.LGRAY)
    reset_btn = Button(140, 208, 4, 8, 'Reset', img, disp, fill=config.LGRAY)

    fxp_btn = Button(45, 65, 3, 6, 'X+1', img, disp, fill=config.LGRAY)
    fxm_btn = Button(105, 65, 3, 6, 'X-1', img, disp, fill=config.LGRAY)
    fyp_btn = Button(45, 95, 3, 6, 'Y+1', img, disp, fill=config.LGRAY)
    fym_btn = Button(105, 95, 3, 6, 'Y-1', img, disp, fill=config.LGRAY)
    fsv_btn = Button(45, 140, 4, 8, 'Save', img, disp, fill=config.LGRAY)
    fzr_btn = Button(130, 140, 4, 8, 'Zero', img, disp, fill=config.LGRAY)


def _card(img, x, y, width, height):
    img.draw_rect(x, y, width, height, config.GRAY, 1)


def draw_UI(img):
    img.draw_rect(0, 0, 320, 24, config.DGRAY, -1)
    LED_btn.draw(img, highlight=bool(config.LED_on))
    CC_btn.draw(img, highlight=config.Maix_State == config.MODE_GRAB)
    EE_btn.draw(img, highlight=config.Maix_State == config.MODE_RING)
    ST_btn.draw(img, highlight=config.Maix_State == config.MODE_STACK)
    QR_btn.draw(img, highlight=config.Maix_State == config.MODE_QR)
    FF_btn.draw(img, highlight=config.Maix_State == config.MODE_IDLE)
    img.draw_string(251, 4, f'{time.fps():.0f}fps', config.WHITE, scale=1, thickness=1)

    img.draw_rect(0, 24, 40, 216, config.DGRAY, -1)
    if config.Maix_State in (config.MODE_GRAB, config.MODE_STACK):
        for index, button in enumerate(color_btns):
            button.draw(img, highlight=(index + 1 == config.Color_Index))
    elif config.Maix_State == config.MODE_RING:
        P1_btn.draw(img, highlight=config.Position_Index == 1)
        P2_btn.draw(img, highlight=config.Position_Index == 2)
        P3_btn.draw(img, highlight=config.Position_Index == 3)

    if config.Maix_State == config.MODE_GRAB:
        _draw_CC(img)
    elif config.Maix_State == config.MODE_RING:
        _draw_EE(img)
    elif config.Maix_State == config.MODE_STACK:
        _draw_STACK(img)
    elif config.Maix_State == config.MODE_QR:
        _draw_QR(img)
    elif config.Maix_State == config.MODE_IDLE:
        _draw_FF(img)


def _draw_CC(img):
    if 1 <= config.Color_Index <= 5:
        threshold = config.LAB_runtime[config.Color_Index]
        name = config.PARAM_NAMES[config.param_idx]
        value_text = f'{name}={threshold[config.param_idx]}'
        value_x = 315 - image.string_size(value_text).width()
        img.draw_string(value_x, 28, value_text, config.YELLOW,
                        scale=1, thickness=1)
    else:
        img.draw_string(95, 28, 'Select Color ->', config.GRAY, scale=1, thickness=1)

    prev_btn.draw(img)
    next_btn.draw(img)
    m10_btn.draw(img)
    m1_btn.draw(img)
    p1_btn.draw(img)
    p10_btn.draw(img)

    _card(img, 45, 92, 265, 105)
    target = config.Target
    img.draw_string(55, 102, f'Center: ({target[0]}, {target[1]})', config.WHITE, scale=1, thickness=1)
    img.draw_string(55, 126, f'Radius: {target[2]}', config.WHITE, scale=1, thickness=1)
    img.draw_string(55, 150, f'Pixels: {target[4]}', config.WHITE, scale=1, thickness=1)
    img.draw_cross(config.hand_x, config.hand_y, config.CYAN, size=8, thickness=2)
    save_btn.draw(img)
    reset_btn.draw(img)


def _draw_FF(img):
    img.draw_string(70, 32, 'Center calibration', config.YELLOW, scale=1, thickness=1)
    fxp_btn.draw(img)
    fxm_btn.draw(img)
    fyp_btn.draw(img)
    fym_btn.draw(img)
    fsv_btn.draw(img)
    fzr_btn.draw(img)
    img.draw_string(45, 175, f'ERROR X: {config.ERROR_x}', config.WHITE, scale=1, thickness=1)
    img.draw_string(45, 195, f'ERROR Y: {config.ERROR_y}', config.WHITE, scale=1, thickness=1)
    img.draw_cross(config.hand_x, config.hand_y, config.CYAN, size=10, thickness=2)


def _draw_EE(img):
    img.draw_string(58, 32, 'Empty ring alignment', config.YELLOW, scale=1, thickness=1)
    img.draw_string(58, 58, f'Task position: {config.Position_Index or "-"}',
                    config.WHITE, scale=1, thickness=1)
    target = config.Target
    if target[3]:
        dx = int(target[0] - config.hand_x)
        dy = int(target[1] - config.hand_y)
        img.draw_string(58, 84, f'dx={dx}  dy={dy}', config.WHITE, scale=1, thickness=1)
        img.draw_string(58, 108, f'confidence={target[4]:.2f}', config.WHITE, scale=1, thickness=1)
    else:
        img.draw_string(58, 84, 'Move close to target ring', config.GRAY, scale=1, thickness=1)
    img.draw_string(52, 184, 'Number locks target ring', config.LGRAY, scale=1, thickness=1)
    img.draw_cross(config.hand_x, config.hand_y, config.CYAN, size=9, thickness=2)


def _draw_STACK(img):
    color_id = config.Color_Index if 0 <= config.Color_Index <= 5 else 0
    name = config.COLOR_NAMES[color_id]
    img.draw_string(58, 32, f'Stack on same color: {name}', config.YELLOW, scale=1, thickness=1)
    target = config.Target
    if target[3]:
        dx = int(target[0] - config.hand_x)
        dy = int(target[1] - config.hand_y)
        img.draw_string(58, 64, f'dx={dx}  dy={dy}', config.WHITE, scale=1, thickness=1)
        img.draw_string(58, 90, f'pixels={target[4]}', config.WHITE, scale=1, thickness=1)
    else:
        img.draw_string(58, 64, 'Lower material not found', config.GRAY, scale=1, thickness=1)
    img.draw_cross(config.hand_x, config.hand_y, config.CYAN, size=9, thickness=2)


def _draw_QR(img):
    img.draw_string(58, 32, 'Scan task QR code', config.YELLOW, scale=1, thickness=1)
    if config.Task_Code:
        img.draw_string(48, 62, config.Task_Code, config.WHITE, scale=1, thickness=1)
    else:
        img.draw_string(58, 62, 'No valid task code', config.GRAY, scale=1, thickness=1)
    plan = config.Task_Plan
    if plan:
        img.draw_string(48, 92, f'B1 color: {plan["first_colors"]}', config.WHITE, scale=1, thickness=1)
        img.draw_string(48, 114, f'B1 pos:   {plan["first_positions"]}', config.WHITE, scale=1, thickness=1)
        img.draw_string(48, 136, f'B2 color: {plan["second_colors"]}', config.WHITE, scale=1, thickness=1)
        img.draw_string(48, 158, f'B2 rough: {plan["second_rough_positions"]}', config.WHITE, scale=1, thickness=1)
        img.draw_string(48, 180, f'B2 stack: {plan["second_stack_positions"]}', config.CYAN, scale=1, thickness=1)
