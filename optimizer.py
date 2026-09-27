"""木料定尺裁切的全局最优求解器。

问题建模
--------
每块原板切出 n 件时的占用长度为::

    sum(零件长度) + (n - 1) * 锯缝宽度 <= 原板长度

令单件权重 ``weight = 零件长度 + kerf``、板容量 ``capacity = board_length + kerf``，
则上式等价于经典装箱约束 ``sum(weight) <= capacity``，本问题即一维装箱问题
（Bin Packing）：在每箱容量相同、箱子数量不超过 available 的前提下装箱。

求解方法
--------
零件总数不超过 12，采用按长度降序的 DFS 精确枚举 + 对称剪枝，保证找到
全局最优，而不是贪心近似：

* 相同当前负载的原板互为对称，只尝试其中一块；
* 板数已不可能优于当前最优解时立即剪枝。

优化目标（字典序）
------------------
1. 原板总价最低 —— 所有原板单价相同，即使用原板数量最少；
2. 板数相同的方案中，各板余料之和最短。

注意板数 k 固定时，余料总和恒为
``k * board_length - sum(零件长度) - (总件数 - k) * kerf``，与具体切法无关，
因此第二目标在第一目标确定后实际上是常量；代码仍严格按两级目标比较，
以完整实现需求并保留清晰语义。
"""


class ValidationError(ValueError):
    """输入数据不满足约束时抛出。"""


def _as_positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name}必须为整数")
    if value <= 0:
        raise ValidationError(f"{name}必须为正整数")
    return value


def _as_nonneg_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name}必须为整数")
    if value < 0:
        raise ValidationError(f"{name}必须为非负整数")
    return value


def _infeasible(reason, lower_bound=None):
    result = {"feasible": False, "reason": reason}
    if lower_bound is not None:
        result["lower_bound"] = lower_bound
    return result


def optimize(board_length, unit_price, available, parts, kerf):
    """求全局最优裁切方案。

    参数
    ----
    board_length : int   原板长度（正整数）
    unit_price   : int   原板单价（正整数）
    available    : int   原板可用数量（正整数）
    parts        : list  零件清单，每项为 (长度, 件数)，长度与件数均为正整数
    kerf         : int   锯缝宽度（非负整数）

    返回
    ----
    dict
        成功时含 ``feasible=True``、逐板方案与合计信息；
        无解时含 ``feasible=False`` 与 ``reason`` 说明。

    抛出
    ----
    ValidationError
        输入不满足题目约束。
    """
    board_length = _as_positive_int(board_length, "原板长度")
    unit_price = _as_positive_int(unit_price, "原板单价")
    available = _as_positive_int(available, "可用数量")
    kerf = _as_nonneg_int(kerf, "锯缝宽度")

    if not isinstance(parts, list) or len(parts) == 0:
        raise ValidationError("请至少填写一种零件")

    items = []
    for idx, row in enumerate(parts, start=1):
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ValidationError(f"第 {idx} 行零件数据格式不正确")
        length = _as_positive_int(row[0], f"第 {idx} 行零件长度")
        qty = _as_positive_int(row[1], f"第 {idx} 行零件件数")
        items.extend([length] * qty)

    total_pieces = len(items)
    if total_pieces > 12:
        raise ValidationError(f"需求总件数为 {total_pieces} 件，不能超过 12 件")

    # 转为装箱模型：weight = 件长 + 锯缝，capacity = 板长 + 锯缝。
    items.sort(reverse=True)
    capacity = board_length + kerf
    weights = [length + kerf for length in items]
    sum_weights = sum(weights)

    # 单件无论如何都放不下：length + kerf > board_length + kerf
    # 等价于 length > board_length（单件上板不产生锯缝）。
    for length, weight in zip(items, weights):
        if weight > capacity:
            return _infeasible(
                f"零件长度 {length} 超过原板长度 {board_length}，无法裁切。"
            )

    lower_bound = -(-sum_weights // capacity)  # ceil(sum / capacity)
    if lower_bound > available:
        return _infeasible(
            f"全部零件连同锯缝的总占位为 {sum_weights}，"
            f"{available} 块原板的总容量仅为 {available * capacity}"
            f"（单块有效容量 {capacity} = 板长 {board_length} + 锯缝 {kerf}），"
            f"至少需要 {lower_bound} 块原板，现有数量不足，无解。",
            lower_bound=lower_bound,
        )

    # ---- DFS 精确搜索 ----
    loads = []          # 每块已启用原板的当前负载
    assignment = [-1] * total_pieces
    best_assignment = None
    best_cost = None    # (板数, 余料合计)

    def cost_of(board_count):
        waste = (
            board_count * board_length
            - sum(items)
            - (total_pieces - board_count) * kerf
        )
        return board_count, waste

    def dfs(i):
        nonlocal best_assignment, best_cost

        # 已用板数超过最优板数，后续不可能反超。
        if best_cost is not None and len(loads) > best_cost[0]:
            return

        if i == total_pieces:
            candidate = cost_of(len(loads))
            if best_cost is None or candidate < best_cost:
                best_cost = candidate
                best_assignment = assignment[:]
            return

        weight = weights[i]

        # 先尝试放入已启用原板；相同负载的板只试一次（对称剪枝）。
        seen_loads = set()
        for board_idx, load in enumerate(loads):
            if load in seen_loads:
                continue
            seen_loads.add(load)
            if load + weight <= capacity:
                loads[board_idx] += weight
                assignment[i] = board_idx
                dfs(i + 1)
                loads[board_idx] -= weight
                assignment[i] = -1

        # 再尝试新开一块原板：即使能放入已有板也必须枚举，因为已有板
        # 后续还要装入其他零件，当前放入可能挤占它们的空间（否则会得到
        # 非最优解）。受可用数量与当前最优板数约束。
        if len(loads) < available:
            # 新开后板数不能比当前最优更多。
            if best_cost is None or len(loads) + 1 <= best_cost[0]:
                assignment[i] = len(loads)
                loads.append(weight)
                dfs(i + 1)
                loads.pop()
                assignment[i] = -1

    dfs(0)

    if best_assignment is None:
        return _infeasible(
            f"在 {available} 块长度为 {board_length} 的原板约束下，"
            "无法为全部零件安排裁切（零件无法组合到这些原板上），无解。",
            lower_bound=lower_bound,
        )

    # ---- 整理逐板结果 ----
    grouped = {}
    for piece_idx, board_idx in enumerate(best_assignment):
        grouped.setdefault(board_idx, []).append(piece_idx)

    boards = []
    total_kerf = 0
    total_waste = 0
    for seq, board_idx in enumerate(sorted(grouped), start=1):
        cut_lengths = [items[piece_idx] for piece_idx in grouped[board_idx]]
        piece_count = len(cut_lengths)
        kerf_total = (piece_count - 1) * kerf
        used_length = sum(cut_lengths) + kerf_total
        leftover = board_length - used_length
        total_kerf += kerf_total
        total_waste += leftover
        boards.append(
            {
                "board_no": seq,
                "cuts": cut_lengths,
                "piece_count": piece_count,
                "kerf_count": piece_count - 1,
                "kerf_total": kerf_total,
                "used_length": used_length,
                "leftover": leftover,
                "price": unit_price,
            }
        )

    board_count = len(boards)
    return {
        "feasible": True,
        "boards": boards,
        "summary": {
            "board_length": board_length,
            "unit_price": unit_price,
            "available": available,
            "board_count": board_count,
            "total_pieces": total_pieces,
            "kerf": kerf,
            "total_cut_length": sum(items),
            "total_kerf": total_kerf,
            "total_waste": total_waste,
            "total_price": board_count * unit_price,
        },
    }
