'''
vision_config.py — 全局常量 + 运行时状态 + 文件读写
'''
from maix import image

# ==================== 文件操作 ====================
def read_file(file_path, line_num):
    try:
        if line_num < 1:
            return 0
        with open(file_path, 'r') as f:
            lines = f.readlines()
        if line_num > len(lines):
            return 0
        content = ''.join(ch for ch in lines[line_num - 1]
                          if ch == '-' or ch.isdigit())
        return int(content) if content else 0
    except Exception:
        return 0


def change_file(file_path, line_num, ins_Cont):
    try:
        if line_num < 1:
            return False
        try:
            with open(file_path, 'r', encoding='utf-8') as rf:
                lines = rf.readlines()
        except (OSError, UnicodeError):
            lines = []
        while len(lines) < line_num:
            lines.append('\n')
        lines[line_num - 1] = str(ins_Cont) + '\n'
        with open(file_path, 'w', encoding='utf-8') as wf:
            wf.writelines(lines)
        return True
    except Exception:
        return False

# ==================== LAB 阈值 ====================
# 参考值: ../pc_vision/lab_color_references.json → MaixPy LAB (L=0~100, A/B=-128~127)
LAB_defaults = {
    1: [20, 90,   15, 80,   -30, 80],    # 红: A 紧 (ref A≈43)
    2: [65, 100,  -25, 25,  30, 80],     # 黄: B 紧 (ref B≈55), L 高
    3: [10, 65,   8, 60,   -80, -40],   # 深蓝: A 为正、B 更负，区分青蓝
    4: [20, 85,   -70, -25, -30, 80],    # 绿: A 紧 (ref A≈-39), A_max 压低防黄
    5: [45, 90,   -30, -5,  -60, -25],  # 浅蓝: 以实测 (63,-13,-41) 为中心留容差
}

# 覆盖旧版黄色默认值，避免点击 Reset 后恢复到过窄阈值。
LAB_defaults[1] = [15, 100, 25, 90, -40, 75]
LAB_defaults[2] = [45, 100, -20, 20, 20, 85]

LAB_runtime = {}
for cid in range(1, 6):
    LAB_runtime[cid] = list(LAB_defaults[cid])

def _load_lab():
    try:
        with open('/root/lab.txt', 'r') as f:
            vals = []
            for line in f.readlines():
                n = ''.join(c for c in line if c == '-' or c.isdigit())
                vals.append(int(n) if n else 0)
            if len(vals) < 24:
                return False
            loaded = {}
            for cid in range(1, 5):
                off = (cid - 1) * 6
                loaded[cid] = vals[off:off + 6]
            loaded[5] = vals[24:30] if len(vals) >= 30 else list(LAB_defaults[5])
            if any(len(values) != 6 for values in loaded.values()):
                return False
            LAB_runtime.update(loaded)
            return True
    except Exception:
        return False


def _save_lab():
    try:
        content = ''.join(f'{value}\n'
                          for cid in range(1, 6)
                          for value in LAB_runtime[cid])
        with open('/root/lab.txt', 'w') as f:
            f.write(content)
        return True
    except Exception:
        return False


def _reset_lab():
    previous = {cid: list(LAB_runtime[cid]) for cid in range(1, 6)}
    for cid in range(1, 6):
        LAB_runtime[cid] = list(LAB_defaults[cid])
    if _save_lab():
        return True
    LAB_runtime.update(previous)
    return False

_load_lab()

# ==================== 颜色定义 ====================
BLACK   = image.Color.from_rgb(0, 0, 0)
WHITE   = image.Color.from_rgb(255, 255, 255)
RED     = image.Color.from_rgb(255, 0, 0)
GREEN   = image.Color.from_rgb(0, 255, 0)
BLUE    = image.Color.from_rgb(0, 0, 255)
YELLOW  = image.Color.from_rgb(255, 255, 0)
CYAN    = image.Color.from_rgb(0, 255, 255)
GRAY    = image.Color.from_rgb(100, 100, 100)
LGRAY   = image.Color.from_rgb(180, 180, 180)
DGRAY   = image.Color.from_rgb(60, 60, 60)

LIGHT_BLUE = image.Color.from_rgb(80, 180, 255)
COLOR_NAMES = ['?', 'R', 'Y', 'DB', 'G', 'LB']
draw_color  = [BLACK, RED, YELLOW, BLUE, GREEN, LIGHT_BLUE]
btn_fill    = [BLACK, RED, YELLOW, BLUE, GREEN, LIGHT_BLUE]
btn_text    = [BLACK, WHITE, BLACK, WHITE, BLACK, BLACK]

PARAM_NAMES = ['L_min', 'L_max', 'A_min', 'A_max', 'B_min', 'B_max']
COLOR_SMOOTH_ALPHA = 0.45
COLOR_HOLD_FRAMES = 2
# 物料圆半径上限（像素）。过大的连通域通常是地面阴影或背景区域，
# 不参与物料识别，避免阴影被当成蓝色物料。
COLOR_MAX_RADIUS_PIXELS = 60
# 3 号蓝色模式直接使用 LAB_runtime[3]，不再套用额外保护边界。
# 5 号模式保留兼容参数，避免旧界面选择浅蓝时运行异常。
LIGHT_BLUE_MIN_L = 45
LIGHT_BLUE_MIN_A = -30
LIGHT_BLUE_MAX_A = -5
LIGHT_BLUE_MIN_B = -60
LIGHT_BLUE_MAX_B = -25
# 绿色和蓝色的 LAB 区间留出间隔，避免同一物料同时通过两套阈值。
GREEN_MAX_A = -30
GREEN_MIN_B = -8
# 只对绿色 A_max 同步显示值与实际保护边界，不改变其他颜色参数。
LAB_defaults[4][3] = min(LAB_defaults[4][3], GREEN_MAX_A)
LAB_runtime[4][3] = min(LAB_runtime[4][3], GREEN_MAX_A)
# 绿色反光短时重捕获：仅在严格阈值刚找到的目标附近使用。
# 这些是待现场验证的候选参数；A 保持负值且不进入黄色的 [-20,20] 区间。
GREEN_GLARE_MAX_L = 100
GREEN_GLARE_MAX_A = -21
GREEN_GLARE_MAX_FRAMES = 2
GREEN_GLARE_ROI_SCALE = 2.5
GREEN_GLARE_MIN_ROI_RADIUS = 45
GREEN_GLARE_MAX_CENTER_SHIFT = 40
# 黄色物料保护边界：保留正 B 色度以排除灰白背景，同时放宽现场色差。
YELLOW_MIN_L = 40
YELLOW_MAX_L_MIN = 55
YELLOW_MIN_A = -20
YELLOW_MAX_A = 20
YELLOW_MIN_B = 20
YELLOW_MAX_B = 85
YELLOW_AREA_THRESHOLD = 300
# 红色物料保护边界：放宽亮度和 B 通道，避免旧 lab.txt 参数过窄。
RED_MIN_L = 10
RED_MAX_L = 100
RED_MIN_A = 25
RED_MAX_A = 90
RED_MIN_B = -40
RED_MAX_B = 80

# ==================== 无颜色同心圆环定位 ====================
RING_CANNY_LOW = 45
RING_CANNY_HIGH = 150
RING_MIN_AREA = 100
RING_MAX_AREA = 22000
RING_MIN_PERIMETER = 45
RING_MIN_CIRCULARITY = 0.55
RING_MAX_AXIS_RATIO = 1.8
RING_MIN_RADIUS = 7
RING_MAX_RADIUS = 95
RING_CENTER_TOLERANCE = 6
RING_RADIUS_SEPARATION = 4
RING_MIN_CONCENTRIC = 3
RING_MAX_CENTER_DISTANCE = 135
RING_SMOOTH_ALPHA = 0.40
RING_HOLD_FRAMES = 10
# 圆环检测包含 Canny、轮廓查找和椭圆拟合，隔帧执行可明显降低 CPU 占用，
# 同时由 RingTracker 保持目标位置，满足实时对中需求。
RING_DETECT_INTERVAL = 2
RING_WARMUP_FRAMES = 2

# 圆环中心的印刷数字识别。首次选择最靠近相机中心的圆环；识别到的数字
# 仅用于后续帧锁定同一圆环，防止多个圆环同框时目标跳变。
RING_DIGIT_LOCK_ENABLED = True
RING_DIGIT_ROI_RATIO = 0.52       # 相对于检测到的最大圆半径的中心数字裁剪半径
RING_DIGIT_MIN_AREA = 10          # 二值化后数字轮廓的最小面积（像素）
RING_DIGIT_MIN_HEIGHT = 7
RING_DIGIT_ONE_MAX_ASPECT = 0.55  # 数字 1 的宽高比上限
RING_DIGIT_MAX_MATCH_SCORE = 1.20
RING_DIGIT_MIN_MATCH_MARGIN = 0.04
RING_ROI_ENABLED = True
RING_ROI_SCALE = 2.2
RING_ROI_MIN_SIZE = 70
RING_ROI_MAX_SIZE = 190
RING_ROI_MAX_LOST = 1
RING_CIRCLE_SAMPLES = 24
RING_MIN_CIRCLE_SUPPORT = 0.30
RING_DIGIT_CONFIRM_CONFIDENCE = 0.45

# ==================== 手爪对中 ====================
WIDTH, HEIGHT = 320, 240
Camera_HEIGHT = 130
Camera_SCALE = Camera_HEIGHT / HEIGHT
try:
    ERROR_x = read_file('/root/error.txt', 1)
    ERROR_y = read_file('/root/error.txt', 2)
except Exception:
    ERROR_x = ERROR_y = 0
hand_x = int(WIDTH / 2 + ERROR_x / Camera_SCALE)
hand_y = int(HEIGHT / 2 + ERROR_y / Camera_SCALE)

def update_hand_xy():
    global hand_x, hand_y
    hand_x = int(WIDTH / 2 + ERROR_x / Camera_SCALE)
    hand_y = int(HEIGHT / 2 + ERROR_y / Camera_SCALE)

# ==================== 运行时状态 ====================
MODE_GRAB = 0xCC           # 原料区：按颜色抓物料
MODE_RING = 0xEE           # 粗加工/暂存：空圆环几何对中
MODE_QR = 0xDD             # 读取比赛任务二维码
MODE_STACK = 0xEC          # 第二批暂存区：对准同颜色第一批物料码垛
MODE_IDLE = 0xFF           # 待机和手爪中心校准

Maix_State  = MODE_IDLE
Color_Index = 0            # 0=NONE, 1=RED, 2=YELLOW, 3=深蓝, 4=GREEN, 5=浅蓝
Position_Index = 0         # 主控根据任务码指定的圆环编号 1/2/3，仅作状态标识
Target      = [0,0,0,0,0]  # CC:[cx,cy,r,color,pixels] EE:[cx,cy,r,slot,confidence]
Task_Code   = ''
Task_Plan   = None
LED_on      = 1             # 相机启动后补光灯常亮
param_idx   = 0            # 当前调节的参数索引
