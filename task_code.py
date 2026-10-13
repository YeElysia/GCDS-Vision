'''比赛二维码任务码解析。

示例 134+123+314+231：
- 第一批颜色顺序：1,3,4
- 第一批粗加工/暂存位置：1,2,3
- 第二批颜色顺序：3,1,4
- 第二批粗加工位置：2,3,1
- 第二批暂存位置：按第一批同颜色物料所在位置自动推导为 2,1,3
'''


COLOR_NAMES = {1: 'red', 2: 'yellow', 3: 'dark_blue', 4: 'green', 5: 'light_blue'}


def _digits(group):
    return [int(char) for char in group]


def parse_task_code(code):
    normalized = ''.join(str(code).strip().split())
    groups = normalized.split('+')
    if len(groups) != 4 or any(len(group) != 3 for group in groups):
        raise ValueError('任务码必须是四组三位数，例如 134+123+314+231')

    first_colors = _digits(groups[0])
    first_positions = _digits(groups[1])
    second_colors = _digits(groups[2])
    second_rough_positions = _digits(groups[3])

    if any(color not in (1, 2, 3, 4, 5) for color in first_colors + second_colors):
        raise ValueError('颜色编号只能是 1=红、2=黄、3=深蓝、4=绿、5=浅蓝')
    if len(set(first_colors)) != 3 or len(set(second_colors)) != 3:
        raise ValueError('每批必须包含三种不同颜色')
    if any(position not in (1, 2, 3) for position in first_positions + second_rough_positions):
        raise ValueError('放置位置编号只能是 1、2、3')
    if len(set(first_positions)) != 3 or len(set(second_rough_positions)) != 3:
        raise ValueError('每组三个放置位置必须是 1、2、3 的排列')

    first_color_to_position = {
        color: first_positions[index]
        for index, color in enumerate(first_colors)
    }
    try:
        second_stack_positions = [
            first_color_to_position[color] for color in second_colors
        ]
    except KeyError as exc:
        raise ValueError('第二批颜色必须能在第一批中找到同颜色码垛物料') from exc

    return {
        'raw': normalized,
        'first_colors': first_colors,
        'first_positions': first_positions,
        'second_colors': second_colors,
        'second_rough_positions': second_rough_positions,
        'second_stack_positions': second_stack_positions,
        'first_pick': list(first_colors),
        'first_rough': list(zip(first_colors, first_positions)),
        'first_temporary': list(zip(first_colors, first_positions)),
        'second_pick': list(second_colors),
        'second_rough': list(zip(second_colors, second_rough_positions)),
        'second_stack': list(zip(second_colors, second_stack_positions)),
    }
