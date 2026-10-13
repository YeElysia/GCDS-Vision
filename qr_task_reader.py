'''读取并稳定确认比赛二维码任务码。'''

from collections import Counter, deque

from task_code import parse_task_code


class QRTaskReader:
    def __init__(self, history_size=5, stable_votes=3):
        self.history = deque(maxlen=history_size)
        self.stable_votes = stable_votes
        self.last_code = None
        self.last_plan = None

    def update(self, img):
        try:
            results = []
            if hasattr(img, 'find_qrcodes'):
                results = img.find_qrcodes()
            elif hasattr(img, 'find_barcodes'):
                results = img.find_barcodes()

            valid = None
            rect = None
            for result in results:
                try:
                    code = result.payload()
                    plan = parse_task_code(code)
                    valid = plan['raw']
                    rect = result.rect()
                    break
                except Exception:
                    continue

            self.history.append(valid)
            votes = Counter(code for code in self.history if code)
            if votes:
                code, count = votes.most_common(1)[0]
                if count >= self.stable_votes and code != self.last_code:
                    self.last_code = code
                    self.last_plan = parse_task_code(code)
                    return self.last_plan, rect, True
            return self.last_plan, rect, False
        except Exception:
            return self.last_plan, None, False

    def reset(self):
        self.history.clear()
        self.last_code = None
        self.last_plan = None
