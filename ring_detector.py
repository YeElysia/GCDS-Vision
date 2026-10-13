'''带 1/2/3 标号的同心圆环定位。

先通过多层同心圆的几何特征找到所有圆环，并选择最靠近相机中心的一组。
圆环中心的印刷数字只用于后续帧锁定同一个目标，避免多圆环同框时跳变。
'''

import cv2
import numpy as np
from maix import image

import vision_config as config


def _center_distance_sq(candidate, center):
    dx = candidate[0] - center[0]
    dy = candidate[1] - center[1]
    return dx * dx + dy * dy


def _to_gray(img):
    if img is None:
        return None
    frame = image.image2cv(img, False, False)
    if frame is None or getattr(frame, 'size', 0) == 0:
        return None
    if len(frame.shape) == 2:
        return frame
    if frame.shape[2] == 1:
        return frame[:, :, 0]
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _find_contours(binary):
    result = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    return result[-2]


def _ellipse_support(edges, center, axes, angle):
    samples = max(8, config.RING_CIRCLE_SAMPLES)
    height, width = edges.shape[:2]
    radians = np.deg2rad(angle)
    cos_angle, sin_angle = np.cos(radians), np.sin(radians)
    hits = 0
    for index in range(samples):
        theta = 2.0 * np.pi * index / samples
        x = center[0] + axes[0] * 0.5 * np.cos(theta) * cos_angle - axes[1] * 0.5 * np.sin(theta) * sin_angle
        y = center[1] + axes[0] * 0.5 * np.cos(theta) * sin_angle + axes[1] * 0.5 * np.sin(theta) * cos_angle
        px, py = int(round(x)), int(round(y))
        x0, x1 = max(0, px - 1), min(width, px + 2)
        y0, y1 = max(0, py - 1), min(height, py + 2)
        if np.any(edges[y0:y1, x0:x1]):
            hits += 1
    return hits / float(samples)


def _ellipse_candidates(gray, offset_x=0, offset_y=0):
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, config.RING_CANNY_LOW, config.RING_CANNY_HIGH)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours = _find_contours(edges)

    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        if area < config.RING_MIN_AREA or area > config.RING_MAX_AREA:
            continue
        if perimeter < config.RING_MIN_PERIMETER or len(contour) < 5:
            continue

        circularity = 4.0 * np.pi * area / max(1.0, perimeter * perimeter)
        if circularity < config.RING_MIN_CIRCULARITY:
            continue

        try:
            center, axes, angle = cv2.fitEllipse(contour)
        except Exception:
            continue
        width, height = axes
        if min(width, height) <= 0:
            continue
        axis_ratio = max(width, height) / min(width, height)
        if axis_ratio > config.RING_MAX_AXIS_RATIO:
            continue

        radius = (width + height) / 4.0
        if radius < config.RING_MIN_RADIUS or radius > config.RING_MAX_RADIUS:
            continue
        if _ellipse_support(edges, center, axes, angle) < config.RING_MIN_CIRCLE_SUPPORT:
            continue
        candidates.append([
            float(center[0]) + offset_x, float(center[1]) + offset_y,
            float(radius), float(circularity), (center, axes, angle)
        ])
    return candidates


def _cluster_concentric(candidates):
    def recenter(cluster):
        items = cluster['items']
        weights = [max(item[3], 0.01) for item in items]
        weight_sum = sum(weights)
        cluster['center'][0] = sum(item[0] * weight for item, weight in zip(items, weights)) / weight_sum
        cluster['center'][1] = sum(item[1] * weight for item, weight in zip(items, weights)) / weight_sum

    clusters = []
    for candidate in sorted(candidates, key=lambda item: item[2], reverse=True):
        matched = None
        for cluster in clusters:
            cx, cy = cluster['center']
            dx = candidate[0] - cx
            dy = candidate[1] - cy
            if dx * dx + dy * dy <= config.RING_CENTER_TOLERANCE ** 2:
                matched = cluster
                break
        if matched is None:
            clusters.append({'center': [candidate[0], candidate[1]], 'items': [candidate]})
        else:
            # 同一条圆边常产生内外两个近似轮廓，半径过近时只保留质量更高者。
            duplicate_index = None
            for index, item in enumerate(matched['items']):
                if abs(item[2] - candidate[2]) < config.RING_RADIUS_SEPARATION:
                    duplicate_index = index
                    break
            if duplicate_index is None:
                matched['items'].append(candidate)
            elif candidate[3] > matched['items'][duplicate_index][3]:
                matched['items'][duplicate_index] = candidate

            recenter(matched)
    return clusters


def _cluster_score(cluster):
    '''给一组同心轮廓评分；不符合几何约束时返回 None。'''
    items = cluster['items']
    if len(items) < config.RING_MIN_CONCENTRIC:
        return None

    quality = sum(item[3] for item in items) / len(items)
    concentric_bonus = min(len(items), 6) * 0.10
    return quality + concentric_bonus


_digit_templates = None


def _make_digit_templates():
    '''生成 1/2/3 的轮廓模板，避免引入重量级 OCR 模型。'''
    templates = {}
    for digit in (1, 2, 3):
        canvas = np.zeros((96, 96), dtype=np.uint8)
        text = str(digit)
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 2.5
        thickness = 7
        (width, height), baseline = cv2.getTextSize(text, font, scale, thickness)
        x = (canvas.shape[1] - width) // 2
        y = (canvas.shape[0] + height) // 2 - baseline
        cv2.putText(canvas, text, (x, y), font, scale, 255, thickness, cv2.LINE_AA)
        contours = _find_contours(canvas)
        templates[digit] = max(contours, key=cv2.contourArea)
    return templates


def _digit_contour(gray, cluster):
    '''返回圆环最内侧数字的轮廓，数字区域不会包含圆环边缘。'''
    cx, cy = cluster['center']
    outer_radius = max(item[2] for item in cluster['items'])
    radius = max(4, int(outer_radius * config.RING_DIGIT_ROI_RATIO))
    x0 = max(0, int(cx) - radius)
    y0 = max(0, int(cy) - radius)
    x1 = min(gray.shape[1], int(cx) + radius + 1)
    y1 = min(gray.shape[0], int(cy) + radius + 1)
    if x1 - x0 < 2 * config.RING_DIGIT_MIN_HEIGHT:
        return None
    if y1 - y0 < 2 * config.RING_DIGIT_MIN_HEIGHT:
        return None

    crop = cv2.GaussianBlur(gray[y0:y1, x0:x1], (3, 3), 0)
    _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 只保留中心区域，排除最内圈圆边和裁剪区域之外的污点。
    mask = np.zeros(binary.shape, dtype=np.uint8)
    local_center = (int(cx) - x0, int(cy) - y0)
    cv2.circle(mask, local_center, max(2, int(radius * 0.82)), 255, -1)
    binary = cv2.bitwise_and(binary, mask)
    contours = _find_contours(binary)

    candidates = []
    max_area = np.pi * (radius * 0.82) ** 2 * 0.70
    for contour in contours:
        area = cv2.contourArea(contour)
        x, y, width, height = cv2.boundingRect(contour)
        if area < config.RING_DIGIT_MIN_AREA or area > max_area:
            continue
        if height < config.RING_DIGIT_MIN_HEIGHT or width < 2:
            continue
        mx = x + width / 2.0
        my = y + height / 2.0
        distance = (mx - local_center[0]) ** 2 + (my - local_center[1]) ** 2
        # 数字应既足够大，又靠近圆心；圆边残留会因距离较大而被抑制。
        candidates.append((area - distance * 0.15, contour))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _read_ring_digit(gray, cluster):
    '''识别单个圆环的正向印刷数字，返回 (digit, confidence)。'''
    global _digit_templates
    contour = _digit_contour(gray, cluster)
    if contour is None:
        return 0, 0.0

    _, _, width, height = cv2.boundingRect(contour)
    aspect = width / float(max(1, height))
    if aspect <= config.RING_DIGIT_ONE_MAX_ASPECT:
        # 场地中的 1 明显窄于 2/3；这一规则比字体模板对缩放更稳定。
        return 1, max(0.0, min(1.0, 1.0 - aspect / config.RING_DIGIT_ONE_MAX_ASPECT))

    if _digit_templates is None:
        _digit_templates = _make_digit_templates()
    scores = []
    for digit in (2, 3):
        score = cv2.matchShapes(contour, _digit_templates[digit], cv2.CONTOURS_MATCH_I1, 0.0)
        scores.append((float(score), digit))
    scores.sort()
    best_score, digit = scores[0]
    second_score = scores[1][0]
    margin = second_score - best_score
    if best_score > config.RING_DIGIT_MAX_MATCH_SCORE:
        return 0, 0.0
    if margin < config.RING_DIGIT_MIN_MATCH_MARGIN:
        return 0, 0.0
    confidence = (1.0 / (1.0 + best_score)) * min(1.0, margin / 0.20)
    return digit, max(0.0, min(1.0, confidence))


def _best_cluster(clusters, gray, camera_center, locked_digit):
    '''选择几何上最稳定且靠近相机中心的圆环。'''
    best = None
    best_distance_sq = None
    best_geometry_score = None
    best_digit = 0
    best_digit_confidence = 0.0
    for cluster in clusters:
        geometry_score = _cluster_score(cluster)
        if geometry_score is None:
            continue
        distance_sq = _center_distance_sq(cluster['center'], camera_center)
        if distance_sq > config.RING_MAX_CENTER_DISTANCE ** 2:
            continue
        digit, digit_confidence = _read_ring_digit(gray, cluster)
        if (best_distance_sq is None or distance_sq < best_distance_sq or
                (distance_sq == best_distance_sq and geometry_score > best_geometry_score)):
            best = cluster
            best_distance_sq = distance_sq
            best_geometry_score = geometry_score
            best_digit = digit
            best_digit_confidence = digit_confidence
    return best, best_geometry_score, best_digit, best_digit_confidence


class RingTracker:
    def __init__(self):
        self.target = None
        self.lost = 0
        self.locked_digit = 0

    def update(self, target, digit=0, digit_confidence=0.0):
        if target is None:
            self.lost += 1
            if self.lost > config.RING_HOLD_FRAMES:
                self.target = None
                self.locked_digit = 0
            return self.target

        self.lost = 0
        if self.target is None:
            self.target = target
        else:
            alpha = config.RING_SMOOTH_ALPHA
            for index in range(3):
                self.target[index] = (
                    alpha * target[index] + (1.0 - alpha) * self.target[index]
                )
            self.target[3] = target[3]
            self.target[4] = target[4]
        if config.RING_DIGIT_LOCK_ENABLED and digit and digit_confidence >= config.RING_DIGIT_CONFIRM_CONFIDENCE:
            self.locked_digit = digit
        return self.target


tracker = RingTracker()


def _lost_detection():
    tracked = tracker.update(None)
    return tracked if tracked is not None else [0, 0, 0, 0, 0]


def _roi_for_target(gray, target):
    if not config.RING_ROI_ENABLED or target is None:
        return None
    if tracker.lost > config.RING_ROI_MAX_LOST:
        return None
    height, width = gray.shape[:2]
    cx, cy, radius = target[:3]
    half = int(max(config.RING_ROI_MIN_SIZE / 2,
                   radius * config.RING_ROI_SCALE))
    half = min(half, config.RING_ROI_MAX_SIZE // 2)
    x0, y0 = max(0, int(cx) - half), max(0, int(cy) - half)
    x1, y1 = min(width, int(cx) + half + 1), min(height, int(cy) + half + 1)
    if x1 - x0 < config.RING_ROI_MIN_SIZE or y1 - y0 < config.RING_ROI_MIN_SIZE:
        return None
    if x0 == 0 or y0 == 0 or x1 == width or y1 == height:
        return None
    return gray[y0:y1, x0:x1], x0, y0


def _detect(gray, camera_center):
    candidates = _ellipse_candidates(gray)
    cluster, score, digit, confidence = _best_cluster(
        _cluster_concentric(candidates), gray, camera_center, tracker.locked_digit
    )
    return cluster, score, digit, confidence


def find_ring(img, position_id):
    '''返回离相机中心最近且几何稳定的 [cx, cy, radius, position_id, confidence]。'''
    try:
        gray = _to_gray(img)
        if gray is None or len(gray.shape) != 2:
            return _lost_detection()

        camera_center = (gray.shape[1] / 2.0, gray.shape[0] / 2.0)
        detected = None
        roi = _roi_for_target(gray, tracker.target)
        if roi is not None:
            roi_gray, offset_x, offset_y = roi
            candidates = _ellipse_candidates(roi_gray, offset_x, offset_y)
            detected = _best_cluster(
                _cluster_concentric(candidates), gray, camera_center,
                tracker.locked_digit,
            )

        if detected is None or detected[0] is None:
            detected = _detect(gray, camera_center)

        cluster, score, digit, digit_confidence = detected
        target = None
        if cluster is not None:
            items = cluster['items']
            target = [
                cluster['center'][0],
                cluster['center'][1],
                max(item[2] for item in items),
                position_id,
                max(0.0, min(1.0, 0.70 * float(score) + 0.30 * digit_confidence)),
            ]
        tracked = tracker.update(target, digit, digit_confidence)
        return tracked if tracked is not None else [0, 0, 0, 0, 0]
    except Exception:
        return _lost_detection()


def reset_tracker():
    tracker.target = None
    tracker.lost = 0
    tracker.locked_digit = 0
