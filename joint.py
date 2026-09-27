"""合格切件错缝拼板预览：把选中的合格切件精确拼成等长多行拼板。

本模块为纯计算，不读写数据库、不修改批次：

* 切件长度取批次冻结值；按等宽木条、接头无长度损耗计算，不裁短；
* 每行从左至右拼到目标行长（行内切件长度之和恰等于目标行长），
  每件切件最多使用一次，允许余件；
* 接缝位置为除末件外的累计长度；相邻行任意两接缝位置差的绝对值
  须不小于最小错缝距离，无接缝行（单件整行）不限制邻行；
* 精确求解：用件数最少的可行排布；并列时逐行比较切件标识序列取
  字典序最小（标识先比板号再比切件号，短前缀在前）。

选件 1～10 件、行数 2～4。求解分两步：先用子集 DP 求出「剩余切件
集合拼 k 行」的最少用件数（忽略错缝），作为 DFS 的精确下界剪枝；
DFS 按（板号, 切件号）升序逐件拼行，完整排布的枚举顺序即逐行标识
序列的字典序，首个达到最少用件数的排布即为答案。
"""

_INF = 10 ** 9


def _subset_sums(lengths):
    """所有子集的长度和：sums[mask] 为 mask 内切件长度之和。"""
    sums = [0] * (1 << len(lengths))
    for mask in range(1, len(sums)):
        low = mask & (-mask)
        sums[mask] = sums[mask ^ low] + lengths[low.bit_length() - 1]
    return sums


def _min_fill_table(sums, target, row_count):
    """min_fill[mask][k]：从 mask 中选件拼 k 行的最少用件数。

    每行长度之和须恰为 target；允许余件（不必用尽 mask 中的切件），
    不可行时为 ``_INF``。忽略错缝约束，用作搜索的精确下界。
    """
    size = len(sums)
    table = [[_INF] * (row_count + 1) for _ in range(size)]
    for mask in range(size):
        table[mask][0] = 0  # 拼 0 行不需要任何切件
    for k in range(1, row_count + 1):
        for mask in range(size):
            if sums[mask] < k * target:
                continue  # 总长不足，保持不可行
            best = _INF
            sub = mask
            while sub:
                if sums[sub] == target:
                    cand = table[mask ^ sub][k - 1] + sub.bit_count()
                    if cand < best:
                        best = cand
                sub = (sub - 1) & mask
            table[mask][k] = best
    return table


def plan_joint(pieces, target, row_count, min_stagger):
    """精确求解错缝拼板排布。

    参数
    ----
    pieces      : list  每项含 ``board_no``、``cut_no``、``length``（冻结长度，
                  正整数）；调用方保证 1～10 件、无重复且板均合格
    target      : int   目标行长（正整数）
    row_count   : int   行数（2～4）
    min_stagger : int   最小错缝距离（非负整数）

    返回
    ----
    dict
        可行时 ``feasible=True``，含逐行 ``rows``（按拼接顺序的切件、接缝
        位置列表与行长）、未用切件 ``unused``（按标识升序）与
        ``used_count``；无解时 ``feasible=False`` 并附 ``reason``。
    """
    n = len(pieces)
    # 按（板号, 切件号）升序排列：DFS 依此顺序逐件枚举，
    # 使完整排布的枚举顺序即逐行标识序列的字典序。
    order = sorted(
        range(n), key=lambda i: (pieces[i]["board_no"], pieces[i]["cut_no"])
    )
    ids = [(pieces[i]["board_no"], pieces[i]["cut_no"]) for i in order]
    lens = [pieces[i]["length"] for i in order]

    sums = _subset_sums(lens)
    min_fill = _min_fill_table(sums, target, row_count)

    full = (1 << n) - 1
    if min_fill[full][row_count] >= _INF:
        return {
            "feasible": False,
            "reason": (
                f"所选切件的长度组合无法拼满 {row_count} 行"
                f"长度均为 {target} 的拼板"
            ),
        }

    best_count = n + 1
    best_rows = None
    rows = []    # 已完成行的切件下标序列
    joints = []  # 已完成行的接缝位置（元组）

    def dfs(row_idx, used_mask, used_count):
        nonlocal best_count, best_rows
        rows_left = row_count - row_idx
        if rows_left == 0:
            # 枚举顺序即字典序：某件数下首个找到的排布即字典序最小者，
            # 之后同件数的排布不必再保留。
            if used_count < best_count:
                best_count = used_count
                best_rows = [list(r) for r in rows]
            return
        # 精确下界剪枝：剩余行用剩余切件的最少件数也追不上当前最优。
        if used_count + min_fill[full ^ used_mask][rows_left] >= best_count:
            return
        build(row_idx, used_mask, used_count, [], [], 0)

    def build(row_idx, used_mask, used_count, cur, cur_joints, psum):
        # 件数下界：本行至少再拼 1 件，后续每行至少 1 件。
        if used_count + len(cur) + 1 + (row_count - row_idx - 1) >= best_count:
            return
        prev_joints = joints[-1] if joints else ()
        for i in range(n):
            if used_mask >> i & 1:
                continue
            ns = psum + lens[i]
            if ns > target:
                continue  # 不裁短：超长即不能入本行
            if ns < target and min_stagger:
                # ns 成为本行接缝：须与上一行每个接缝错开 min_stagger。
                if any(abs(ns - j) < min_stagger for j in prev_joints):
                    continue
            mask2 = used_mask | (1 << i)
            if ns == target:
                # 本行拼满：末件不产生接缝。
                rows.append(cur + [i])
                joints.append(tuple(cur_joints))
                dfs(row_idx + 1, mask2, used_count + len(cur) + 1)
                joints.pop()
                rows.pop()
            else:
                # 剩余切件总长不足以拼满本行：剪枝。
                if sums[full ^ mask2] < target - ns:
                    continue
                cur.append(i)
                cur_joints.append(ns)
                build(row_idx, mask2, used_count, cur, cur_joints, ns)
                cur_joints.pop()
                cur.pop()

    dfs(0, 0, 0)

    if best_rows is None:
        return {
            "feasible": False,
            "reason": (
                f"所选切件在最小错缝距离 {min_stagger} 的约束下"
                "不存在可行的拼板排布"
            ),
        }

    used_idx = set()
    out_rows = []
    for row_no, row in enumerate(best_rows, start=1):
        seq = []
        row_joints = []
        cum = 0
        for pos, i in enumerate(row):
            cum += lens[i]
            if pos < len(row) - 1:
                row_joints.append(cum)
            seq.append(
                {"board_no": ids[i][0], "cut_no": ids[i][1], "length": lens[i]}
            )
            used_idx.add(i)
        out_rows.append(
            {
                "row_no": row_no,
                "piece_count": len(row),
                "total_length": cum,
                "pieces": seq,
                "joints": row_joints,
            }
        )

    unused = [
        {"board_no": ids[i][0], "cut_no": ids[i][1], "length": lens[i]}
        for i in range(n)
        if i not in used_idx
    ]
    return {
        "feasible": True,
        "used_count": len(used_idx),
        "rows": out_rows,
        "unused": unused,
    }
