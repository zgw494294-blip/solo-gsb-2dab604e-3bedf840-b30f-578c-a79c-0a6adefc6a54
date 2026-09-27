"""批次实测尺寸复核：把实测切件精确匹配给冻结需求件。

打开核销批次后，可仅为「合格」原板的切件录入实测长度与公差。本模块为纯计算，
不读写数据库、不修改批次：

* 冻结需求按零件录入顺序展开为单件（从 1 开始编号）；
* 实测件仅可分给长度差绝对值不超过公差的需求件，每件至多使用一次，
  未匹配的实测件记为未分配；
* 精确求解（分支定界），目标依次为：

  1. 满足（匹配）件数最多；
  2. 件数相同的方案中，总长度偏差（|实测 − 需求| 之和）最小；
  3. 仍并列时，实测件按板号、切件序号排列，取其需求件序号序列字典序最小者
     （未分配排在最后）。

需求总件数不超过 12。DFS 按需求件序号升序枚举每件去向（未分配最后尝试），
每个节点先用 Kuhn 最大匹配求件数上界快速剪枝，再用子集 DP 精确求出剩余实测件
在空闲需求件上的（最大件数，最小偏差），与字典序前缀共同决定子树是否可能
超越当前最优。
"""

UNASSIGNED = None  # 未分配在字典序比较中排在任何需求件序号之后


def expand_demands(frozen_parts):
    """把冻结需求按零件录入顺序展开为单件，序号从 1 开始。

    返回 ``[(需求件序号, 需求长度), ...]``，同一零件的多件连续排列。
    """
    demands = []
    seq = 1
    for row in frozen_parts:
        for _ in range(row["quantity"]):
            demands.append((seq, row["length"]))
            seq += 1
    return demands


def _augment(piece_idx, candidate_sets, matched_to, used_demands, visited):
    """Kuhn 增广路：为剩余实测件 piece_idx 在未占用需求件上找增广路。"""
    for j, _ in candidate_sets[piece_idx]:
        if used_demands[j] or visited[j]:
            continue
        visited[j] = True
        if matched_to[j] is None or _augment(
            matched_to[j], candidate_sets, matched_to, used_demands, visited
        ):
            matched_to[j] = piece_idx
            return True
    return False


def _cardinality_upper_bound(pos, count, used_demands, candidate_sets, demand_count):
    """前缀确定后整体匹配件数的精确上界（前缀件数 + 剩余件的 Kuhn 最大匹配）。"""
    matched_to = [None] * demand_count
    extra = 0
    for i in range(pos, len(candidate_sets)):
        visited = [False] * demand_count
        if _augment(i, candidate_sets, matched_to, used_demands, visited):
            extra += 1
    return count + extra


def _residual_optimum(pos, used_demands, candidates):
    """剩余实测件在空闲需求件上的最优（最大件数，最小偏差）。

    子集 DP：dp[空闲需求件占用掩码] = 已处理剩余实测件中能匹配的最小偏差，
    件数由已用需求件数体现；最后在全部掩码中取件数最大、偏差最小者。
    """
    # 仅保留空闲需求件，映射到压缩位下标。
    free_idx = [j for j in range(len(used_demands)) if not used_demands[j]]
    compressed = {j: bit for bit, j in enumerate(free_idx)}
    rows = []
    for i in range(pos, len(candidates)):
        opts = [
            (compressed[j], diff)
            for j, diff in candidates[i]
            if not used_demands[j]
        ]
        rows.append(opts)

    full_mask = 1 << len(free_idx)
    dp = {0: 0}
    for opts in rows:
        nxt = dict(dp)  # 本实测件不分配：掩码与偏差不变。
        for mask, dev in dp.items():
            for bit, diff in opts:
                if mask & (1 << bit):
                    continue
                new_mask = mask | (1 << bit)
                new_dev = dev + diff
                if new_mask not in nxt or new_dev < nxt[new_mask]:
                    nxt[new_mask] = new_dev
        dp = nxt

    best_count = 0
    best_dev = 0
    for mask, dev in dp.items():
        cnt = mask.bit_count()
        if cnt > best_count or (cnt == best_count and dev < best_dev):
            best_count = cnt
            best_dev = dev
    return best_count, best_dev


def match_measurements(demands, measurements, tolerance):
    """精确求解实测件到需求件的最优匹配。

    参数
    ----
    demands      : list  ``[(需求件序号, 需求长度), ...]``，序号从 1 开始
    measurements : list  每项含 ``board_no``、``cut_no``、``actual_length``、
                   ``planned_length``；调用方须保证板均合格、切件存在且无重复
    tolerance    : int   非负公差

    返回
    -------
    dict
        ``assignments`` 与 measurements 同序（按板号、切件序号排序），每项为
        ``{board_no, cut_no, planned_length, actual_length, assigned,
        demand_no, demand_length, deviation}``，未匹配时需求相关字段为 ``None``；
        另含 ``matched_count`` 与 ``total_deviation``。
    """
    n = len(demands)
    big = n + 1  # 未分配的字典序值，大于任意需求件序号

    # 实测件按（板号，切件序号）排列；此即字典序比较的固定顺序。
    ordered = sorted(measurements, key=lambda m: (m["board_no"], m["cut_no"]))
    k = len(ordered)

    # candidates[i]：实测件 i 可分给的需求件 [(内部下标, 偏差), ...]，按下标升序，
    # 保证 DFS 分支按需求件序号从小到大枚举。
    candidates = []
    for m in ordered:
        row = []
        for idx, (_, demand_length) in enumerate(demands):
            diff = abs(m["actual_length"] - demand_length)
            if diff <= tolerance:
                row.append((idx, diff))
        candidates.append(row)

    # best =（最优件数, 最优偏差, 序号序列）；逐分量按“件数最大、偏差最小、
    # 序列字典序最小”比较。
    best_count = None
    best_deviation = None
    best_sequence = None
    best_assignment = None

    choice = [UNASSIGNED] * k
    used_demands = [False] * n

    def dfs(i, count, deviation):
        nonlocal best_count, best_deviation, best_sequence, best_assignment

        if i == k:
            sequence = tuple(
                big if choice[p] is UNASSIGNED else choice[p] for p in range(k)
            )
            if (
                best_count is None
                or count > best_count
                or (count == best_count and deviation < best_deviation)
                or (
                    count == best_count
                    and deviation == best_deviation
                    and sequence < best_sequence
                )
            ):
                best_count = count
                best_deviation = deviation
                best_sequence = sequence
                best_assignment = choice[:]
            return

        # 廉价剪枝：件数上界连当前最优都追不上，直接返回。
        if best_count is not None:
            upper = _cardinality_upper_bound(
                i, count, used_demands, candidates, n
            )
            if upper < best_count:
                return

        # 精确剪枝：剩余实测件在空闲需求件上的最优（件数, 偏差）。
        rest_count, rest_dev = _residual_optimum(i, used_demands, candidates)
        final_count = count + rest_count
        final_dev = deviation + rest_dev

        # 与当前最优的字典序前缀关系：-1 前缀更小 / 1 更大 / 0 前缀完全相同。
        lex_cmp = 0
        if best_sequence is not None:
            for p in range(i):
                cur = big if choice[p] is UNASSIGNED else choice[p]
                if cur != best_sequence[p]:
                    lex_cmp = -1 if cur < best_sequence[p] else 1
                    break

        if best_count is not None:
            if final_count < best_count:
                return  # 剩余件无论怎么分都补不齐件数。
            if final_count == best_count:
                if final_dev > best_deviation:
                    return  # 件数持平而偏差更大（这是剩余可达的最小偏差）。
                if final_dev == best_deviation and lex_cmp > 0:
                    # 件数、偏差皆持平：前缀更大则字典序必败；前缀更小仍可能
                    # 反超（后续位继续比较），不能剪。
                    return
            # final_count > best_count 时件数严格占优；或偏差严格更小时，
            # 即便前缀更大也可能反超：均继续搜索。

        # 先枚举分给某个空闲且合格的需求件（序号升序），未分配最后尝试：
        # 首个完整解即沿字典序最小方向，便于后续剪枝。
        for j, diff in candidates[i]:
            if used_demands[j]:
                continue
            used_demands[j] = True
            choice[i] = j
            dfs(i + 1, count + 1, deviation + diff)
            choice[i] = UNASSIGNED
            used_demands[j] = False

        # 本件不分配。
        choice[i] = UNASSIGNED
        dfs(i + 1, count, deviation)

    dfs(0, 0, 0)

    assignments = []
    total_deviation = 0
    for m, j in zip(ordered, best_assignment):
        item = {
            "board_no": m["board_no"],
            "cut_no": m["cut_no"],
            "planned_length": m["planned_length"],
            "actual_length": m["actual_length"],
            "assigned": j is not UNASSIGNED,
            "demand_no": None,
            "demand_length": None,
            "deviation": None,
        }
        if j is not UNASSIGNED:
            demand_no, demand_length = demands[j]
            item["demand_no"] = demand_no
            item["demand_length"] = demand_length
            item["deviation"] = abs(m["actual_length"] - demand_length)
            total_deviation += item["deviation"]
        assignments.append(item)

    return {
        "assignments": assignments,
        "matched_count": best_count,
        "total_deviation": total_deviation,
    }
