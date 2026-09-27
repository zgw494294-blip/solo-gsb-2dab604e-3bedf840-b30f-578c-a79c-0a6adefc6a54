"""多订单合板费用的 Shapley 精确分摊。

流程
----
1. 对 2～4 个订单的每个子集精确求解合板最低原板总价：把子集内各订单的
   零件合并，用 ``optimizer.optimize`` 求全局最优裁切方案，
   费用 = 使用原板数 × 原板单价；空集费用恒为 0；
2. 按所有订单加入次序（n! 种排列）的平均边际费用计算每个订单的
   Shapley 分摊值，全程使用 ``fractions.Fraction`` 有理数运算；
3. 把分摊值换算为“分”取整：先逐单向下取整，剩余的分按小数余数降序
   补足（余数相同按订单录入顺序），保证各单应付之和恰好等于合板最优总价。

全部订单合板无解时不进行分摊，直接返回无解信息。
"""

import math
from fractions import Fraction
from itertools import permutations

from optimizer import ValidationError, _as_nonneg_int, _as_positive_int, optimize

MIN_ORDERS = 2
MAX_ORDERS = 4
MAX_TOTAL_PIECES = 12


def _validate_orders(orders):
    """校验订单结构，返回 [(名称, [(长度, 件数), ...]), ...]。"""
    if not isinstance(orders, list) or not MIN_ORDERS <= len(orders) <= MAX_ORDERS:
        raise ValidationError(f"订单数量须为 {MIN_ORDERS}～{MAX_ORDERS} 个")

    validated = []
    total_pieces = 0
    for idx, order in enumerate(orders, start=1):
        if not isinstance(order, (list, tuple)) or len(order) != 2:
            raise ValidationError(f"第 {idx} 个订单格式不正确")
        name, parts = order
        if not isinstance(name, str) or not name.strip():
            raise ValidationError(f"第 {idx} 个订单的名称不能为空")
        name = name.strip()

        if not isinstance(parts, list) or len(parts) == 0:
            raise ValidationError(f"订单「{name}」至少填写一种零件")
        rows = []
        for row_idx, row in enumerate(parts, start=1):
            if not isinstance(row, (list, tuple)) or len(row) != 2:
                raise ValidationError(f"订单「{name}」第 {row_idx} 行零件数据格式不正确")
            length = _as_positive_int(row[0], f"订单「{name}」第 {row_idx} 行零件长度")
            qty = _as_positive_int(row[1], f"订单「{name}」第 {row_idx} 行零件件数")
            rows.append((length, qty))
            total_pieces += qty
        validated.append((name, rows))

    if total_pieces > MAX_TOTAL_PIECES:
        raise ValidationError(
            f"全部订单合计 {total_pieces} 件，不能超过 {MAX_TOTAL_PIECES} 件"
        )
    return validated


def _subset_costs(orders, board_length, unit_price, available, kerf):
    """求每个订单子集的合板最低原板总价。

    返回 ``(costs, full_result)``：``costs`` 为 {frozenset: Fraction}，
    含空集费用 0；全集无解时 ``costs`` 为 None，``full_result`` 为全集的
    无解结果（含 reason）。
    """
    n = len(orders)

    # 先解全集：全集无解则直接返回，不生成分摊。
    all_parts = [row for _, rows in orders for row in rows]
    full_result = optimize(board_length, unit_price, available, all_parts, kerf)
    if not full_result["feasible"]:
        return None, full_result

    costs = {frozenset(): Fraction(0)}
    for mask in range(1, (1 << n) - 1):
        subset = frozenset(i for i in range(n) if mask & (1 << i))
        parts = [row for i in sorted(subset) for row in orders[i][1]]
        result = optimize(board_length, unit_price, available, parts, kerf)
        if not result["feasible"]:
            # 全集可行时子集必可行（从全集可行方案中删去其余零件即得子集
            # 可行方案），此分支仅为防御。
            raise RuntimeError("子集裁切求解异常")
        costs[subset] = Fraction(result["summary"]["total_price"])
    costs[frozenset(range(n))] = Fraction(full_result["summary"]["total_price"])
    return costs, full_result


def _shapley(costs, n):
    """按全部 n! 种加入次序的平均边际费用求各订单的 Shapley 分摊值。"""
    shares = [Fraction(0) for _ in range(n)]
    for perm in permutations(range(n)):
        subset = frozenset()
        prev = costs[subset]
        for i in perm:
            subset = subset | {i}
            current = costs[subset]
            shares[i] += current - prev
            prev = current
    divisor = Fraction(math.factorial(n))
    return [share / divisor for share in shares]


def _round_to_fen(shares, total_fen):
    """把有理数分摊值（元）换算成分并取整，返回每单应付的分。

    先逐单向下取整；剩余的分按小数余数降序逐个补足，余数相同按订单
    录入顺序，保证各单应付之和等于 ``total_fen``。
    """
    exact_fen = [share * 100 for share in shares]
    pay = [value.numerator // value.denominator for value in exact_fen]
    leftover = total_fen - sum(pay)
    # 小数余数降序；余数相同（含同为 0）时保持录入顺序。
    fracs = [exact_fen[i] - pay[i] for i in range(len(shares))]
    order = sorted(range(len(shares)), key=lambda i: (-fracs[i], i))
    for k in range(leftover):
        pay[order[k]] += 1
    return pay


def allocate(board_length, unit_price, available, kerf, orders):
    """求多订单合板的 Shapley 费用分摊。

    参数与 ``optimizer.optimize`` 相同，另加 ``orders``：
    [(订单名称, [(零件长度, 件数), ...]), ...]，须为 2～4 个订单。

    返回
    ----
    dict
        可行时含 ``feasible=True``、合板总价与各单分摊（精确值 + 应付分）；
        全部订单合板无解时含 ``feasible=False`` 与 ``reason``，不生成分摊。

    抛出
    ----
    ValidationError
        输入不满足约束。
    """
    board_length = _as_positive_int(board_length, "原板长度")
    unit_price = _as_positive_int(unit_price, "原板单价")
    available = _as_positive_int(available, "可用数量")
    kerf = _as_nonneg_int(kerf, "锯缝宽度")
    orders = _validate_orders(orders)

    n = len(orders)
    costs, full_result = _subset_costs(orders, board_length, unit_price, available, kerf)
    if costs is None:
        # 全部订单合板无解：返回无解，不生成分摊。
        result = {"feasible": False, "reason": full_result["reason"]}
        if "lower_bound" in full_result:
            result["lower_bound"] = full_result["lower_bound"]
        return result

    shares = _shapley(costs, n)
    total_price = full_result["summary"]["total_price"]
    total_fen = total_price * 100
    pay_fen = _round_to_fen(shares, total_fen)

    return {
        "feasible": True,
        "summary": {
            "board_length": board_length,
            "unit_price": unit_price,
            "available": available,
            "kerf": kerf,
            "order_count": n,
            "board_count": full_result["summary"]["board_count"],
            "total_pieces": full_result["summary"]["total_pieces"],
            "total_price": total_price,
            "total_fen": total_fen,
        },
        "orders": [
            {
                "name": orders[i][0],
                "share_exact": str(shares[i]),  # 精确分摊值（元），分数形式
                "pay_fen": pay_fen[i],  # 最终应付（分）
            }
            for i in range(n)
        ],
    }
