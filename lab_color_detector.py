'''基于 LAB 阈值的颜色色块检测。'''
import vision_config as config


class Color_LAB_Threshold:
    def __init__(self, color_id, key_param):
        self.color_id = color_id
        self.key_param = key_param
        self.LostCnt = 0
        self.MaxLost = 30
        self.Step = 2

    def alter(self, detected):
        threshold = config.LAB_runtime[self.color_id]
        if detected:
            self.LostCnt = 0
            return

        self.LostCnt += 1
        if self.LostCnt <= self.MaxLost:
            return
        self.LostCnt = 0

        if self.key_param == 'A':
            if self.color_id == 1:
                threshold[2] = max(threshold[2] - self.Step, 0)
                threshold[3] = min(threshold[3] + self.Step, 100)
            elif self.color_id == 4:
                threshold[2] = max(threshold[2] - self.Step, -100)
                threshold[3] = min(threshold[3] + self.Step, config.GREEN_MAX_A)
        elif self.key_param == 'B':
            if self.color_id == 2:
                threshold[4] = max(threshold[4] - self.Step, -30)
                threshold[5] = min(threshold[5] + self.Step, 100)
            elif self.color_id == 3:
                threshold[4] = max(threshold[4] - self.Step, -80)
                threshold[5] = min(threshold[5] + self.Step, 5)
            elif self.color_id == 5:
                threshold[4] = max(threshold[4] - self.Step, -100)
                threshold[5] = min(threshold[5] + self.Step,
                                   config.LIGHT_BLUE_MAX_B)


adapts = {
    1: Color_LAB_Threshold(1, 'A'),
    2: Color_LAB_Threshold(2, 'B'),
    3: Color_LAB_Threshold(3, 'B'),
    4: Color_LAB_Threshold(4, 'A'),
    5: Color_LAB_Threshold(5, 'B'),
}


class ColorTargetTracker:
    def __init__(self):
        self.target = None
        self.lost = 0

    def update(self, target):
        if target[3] == 0:
            self.lost += 1
            if self.lost > config.COLOR_HOLD_FRAMES:
                self.target = None
            return self.target if self.target is not None else target

        self.lost = 0
        if self.target is None:
            self.target = list(target)
        else:
            alpha = config.COLOR_SMOOTH_ALPHA
            for index in range(3):
                self.target[index] = (
                    alpha * target[index] + (1.0 - alpha) * self.target[index]
                )
            self.target[3] = target[3]
            self.target[4] = target[4]
        return self.target


trackers = {color_id: ColorTargetTracker() for color_id in range(1, 6)}

# 补偿锚点只来自严格阈值检测，宽阈值结果不能刷新锚点或续期。
_green_anchor = None
_green_glare_frames = 0


def _runtime_threshold(color_index):
    """返回当前颜色的运行时 LAB 阈值。"""
    threshold = list(config.LAB_runtime[color_index])
    if color_index == 1:
        threshold[0] = min(threshold[0], config.RED_MIN_L)
        threshold[1] = max(threshold[1], config.RED_MAX_L)
        threshold[2] = max(threshold[2], config.RED_MIN_A)
        threshold[3] = max(threshold[3], config.RED_MAX_A)
        threshold[4] = min(threshold[4], config.RED_MIN_B)
        threshold[5] = max(threshold[5], config.RED_MAX_B)
    elif color_index == 5:
        threshold[0] = max(threshold[0], config.LIGHT_BLUE_MIN_L)
        threshold[2] = max(threshold[2], config.LIGHT_BLUE_MIN_A)
        threshold[3] = min(threshold[3], config.LIGHT_BLUE_MAX_A)
        threshold[4] = max(threshold[4], config.LIGHT_BLUE_MIN_B)
        threshold[5] = min(threshold[5], config.LIGHT_BLUE_MAX_B)
    elif color_index == 2:
        threshold[0] = max(config.YELLOW_MIN_L,
                           min(threshold[0], config.YELLOW_MAX_L_MIN))
        threshold[1] = max(threshold[1], 85)
        threshold[2] = max(threshold[2], config.YELLOW_MIN_A)
        threshold[3] = min(threshold[3], config.YELLOW_MAX_A)
        # 旧版保存的 B_min=30 过严，统一回落到 20，避免黄色再次漏检。
        threshold[4] = config.YELLOW_MIN_B
        threshold[5] = min(threshold[5], config.YELLOW_MAX_B)
    elif color_index == 4:
        threshold[3] = min(threshold[3], config.GREEN_MAX_A)
        threshold[4] = max(threshold[4], config.GREEN_MIN_B)
    return threshold


def _green_glare_blob(img, merge):
    '''严格检测短时失败时，在最近绿色目标附近搜索，保持原面积门槛。'''
    global _green_glare_frames
    try:
        if _green_anchor is None or _green_glare_frames >= config.GREEN_GLARE_MAX_FRAMES:
            return None
        _green_glare_frames += 1
        cx, cy, radius = _green_anchor
        reach = max(config.GREEN_GLARE_MIN_ROI_RADIUS,
                    int(radius * config.GREEN_GLARE_ROI_SCALE))
        x0, y0 = max(0, int(cx) - reach), max(0, int(cy) - reach)
        x1 = min(img.width(), int(cx) + reach + 1)
        y1 = min(img.height(), int(cy) + reach + 1)
        if x1 <= x0 or y1 <= y0:
            return None
        threshold = _runtime_threshold(4)
        threshold[1] = max(threshold[1], config.GREEN_GLARE_MAX_L)
        threshold[3] = max(threshold[3], config.GREEN_GLARE_MAX_A)
        blobs = img.find_blobs(
            [threshold], invert=False, roi=[x0, y0, x1 - x0, y1 - y0],
            area_threshold=300, pixels_threshold=300, merge=merge, margin=10,
        )
        valid = [blob for blob in (blobs or [])
                 if max(blob.w(), blob.h()) * 0.5 <= config.COLOR_MAX_RADIUS_PIXELS
                 and (blob.cx() - cx) ** 2 + (blob.cy() - cy) ** 2
                 <= config.GREEN_GLARE_MAX_CENTER_SHIFT ** 2]
        if not valid:
            return None
        return min(valid, key=lambda blob: (blob.cx() - cx) ** 2 + (blob.cy() - cy) ** 2)
    except Exception:
        return None


def find_color(img, color_index, merge=True):
    global _green_anchor, _green_glare_frames
    try:
        if color_index != 4:
            _green_anchor = None
            _green_glare_frames = 0
        if color_index not in trackers:
            return [0, 0, 0, 0, 0]

        min_blob_pixels = (
            config.YELLOW_AREA_THRESHOLD if color_index == 2 else 300
        )
        blobs = img.find_blobs(
            [_runtime_threshold(color_index)],
            invert=False,
            area_threshold=min_blob_pixels,
            pixels_threshold=min_blob_pixels,
            merge=merge,
            margin=10,
        )
        if not blobs and color_index != 4:
            return trackers[color_index].update([0, 0, 0, 0, 0])

        valid_blobs = [
            blob for blob in (blobs or [])
            if max(blob.w(), blob.h()) * 0.5 <= config.COLOR_MAX_RADIUS_PIXELS
        ]
        if color_index == 4:
            if valid_blobs:
                strict_best = max(valid_blobs, key=lambda blob: blob.area())
                _green_anchor = (strict_best.cx(), strict_best.cy(),
                                 max(strict_best.w(), strict_best.h()) / 2.0)
                _green_glare_frames = 0
            else:
                glare_blob = _green_glare_blob(img, merge)
                if glare_blob is not None:
                    valid_blobs = [glare_blob]
        if not valid_blobs:
            return trackers[color_index].update([0, 0, 0, 0, 0])

        best = max(valid_blobs, key=lambda blob: blob.area())
        radius = int(max(best.w(), best.h()) / 2)
        target = [best.cx(), best.cy(), radius, color_index, best.area()]
        if target[2] < 0 or target[4] < 0:
            return [0, 0, 0, 0, 0]
        return trackers[color_index].update(target)
    except Exception:
        return [0, 0, 0, 0, 0]


def reset_trackers():
    global _green_anchor, _green_glare_frames
    _green_anchor = None
    _green_glare_frames = 0
    for tracker in trackers.values():
        tracker.target = None
        tracker.lost = 0
