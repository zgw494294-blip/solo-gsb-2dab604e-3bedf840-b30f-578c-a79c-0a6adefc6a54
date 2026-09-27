"""锯机作业排程。

在单份清单的**全局最优裁切结果**确定后，把每块原板视为不可拆分的作业，
分配给 2～4 台异速锯机加工：

* 每块原板在某台机器上的作业耗时为
  ``准备分钟 + 本板切件数 × 该机每件切割分钟``；
* 同一台机器按原板编号 1, 2, ... 的顺序连续加工，首块自该机
  「最早可用分钟」起，后续各块紧接前一块完工；
* 优化目标：已接单机台（至少分到一块原板）的最晚完工分钟
  （makespan）最小，未分配原板的闲置机台不计入整体完工时间；
* 并列目标：按原板编号顺序排列的机台编号序列字典序最小
  （机台按录入顺序从 1 编号）。

原板数不超过 12、机器数不超过 4，采用逐板决定机台的 DFS 精确枚举，
配合同构机台对称剪枝、到达状态记忆与工作量下界剪枝，保证全局最优
而非贪心近似；DFS 按机台编号升序展开子节点，故首次到达的最优工期叶
即字典序最小方案，代码仍显式比较 ``(工期, 机台序列)`` 以保留清晰语义。

排料无解时直接返回无解信息，不生成排程。
"""

from optimizer import ValidationError, _as_nonneg_int, _as_positive_int, optimize

MIN_MACHINES = 2
MAX_MACHINES = 4


def _validate_scheduling(setup_minutes, machines):
    """校验排程参数，返回 (准备分钟, [(最早可用分钟, 每件切割分钟), ...])。"""
    setup = _as_nonneg_int(setup_minutes, "每板准备分钟")

    if not isinstance(machines, list) or not MIN_MACHINES <= len(machines) <= MAX_MACHINES:
        raise ValidationError(f"锯机数量须为 {MIN_MACHINES}～{MAX_MACHINES} 台")

    validated = []
    for idx, machine in enumerate(machines, start=1):
        if not isinstance(machine, dict):
            raise ValidationError(f"第 {idx} 台锯机数据格式不正确")
        ready = _as_nonneg_int(
            machine.get("ready_minutes"), f"第 {idx} 台锯机最早可用分钟"
        )
        cut = _as_positive_int(
            machine.get("cut_minutes"), f"第 {idx} 台锯机每件切割分钟"
        )
        validated.append((ready, cut))
    return setup, validated


def _greedy_assignment(piece_counts, ready, cut, setup):
    """列表调度贪心：每块板分给能让它最早完工的机器，并列取编号最小者。

    返回 (机台序列, 工期)，作为精确搜索的初始上界；工期只统计实际
    分到原板的机台，闲置机台的最早可用分钟不计入整体完工时间。
    """
    m = len(ready)
    clocks = ready[:]
    used = [False] * m
    assignment = []
    for pieces in piece_counts:
        chosen = 0
        earliest = None
        for j in range(m):
            finish = clocks[j] + setup + pieces * cut[j]
            if earliest is None or finish < earliest:
                chosen = j
                earliest = finish
        clocks[chosen] = earliest
        used[chosen] = True
        assignment.append(chosen)
    makespan = max(clocks[j] for j in range(m) if used[j])
    return assignment, makespan


def _best_assignment(piece_counts, ready, cut, setup):
    """精确求已接单机台最晚完工分钟最小的分配，并列取机台序列字典序最小者。

    未分到原板的闲置机台不计入整体完工时间。
    返回 (机台序列[零基], 最优工期)。
    """
    n = len(piece_counts)
    m = len(ready)
    total_pieces = sum(piece_counts)
    min_cut = min(cut)
    # 最终接单的机台至多 min(m, n) 台（每台至少分到一块板），
    # 作为工作量下界的除数。
    max_busy = min(m, n)

    # prefix_pieces[i] = 前 i 块板的切件数之和。
    prefix_pieces = [0]
    for pieces in piece_counts:
        prefix_pieces.append(prefix_pieces[-1] + pieces)

    best_assignment, best_makespan = _greedy_assignment(
        piece_counts, ready, cut, setup
    )

    clocks = ready[:]          # 各机当前（下一块）可开工分钟
    assignment = [-1] * n
    reached = set()            # 已充分展开的 (深度, 各机时刻) 状态

    def dfs(i):
        nonlocal best_assignment, best_makespan

        state = (i, tuple(clocks))
        if state in reached:
            return
        reached.add(state)

        # 每块板耗时 = 准备 + 件数 × 切割 ≥ 1 分钟，故时刻超过最早可用
        # 分钟的机器即已接单机台；状态 (i, clocks) 完全确定接单集合，
        # 到达状态记忆不受影响。闲置机台不计入整体完工时间。
        active = [j for j in range(m) if clocks[j] != ready[j]]

        if i == n:
            makespan = max(clocks[j] for j in active)
            candidate = tuple(assignment)
            if makespan < best_makespan or (
                makespan == best_makespan and candidate < tuple(best_assignment)
            ):
                best_makespan = makespan
                best_assignment = assignment[:]
            return

        # ---- 工作量下界剪枝 ----
        # 已接单机台的时刻只增不减，故工期不小于其中最大时刻；剩余板的
        # 准备合计（每板恰一次）与切割合计（按最快机速低估）全部落在
        # 最终接单的机台上，这些机台的时刻总和 ≥ 已接单时刻合计 + 剩余
        # 工作量，而接单机器至多 max_busy 台，故最晚完工 ≥ 该总和除以
        # 台数向上取整。闲置机台的最早可用分钟不计入下界。
        remaining_boards = n - i
        remaining_pieces = total_pieces - prefix_pieces[i]
        total_work = (
            sum(clocks[j] for j in active)
            + remaining_boards * setup
            + remaining_pieces * min_cut
        )
        lower_bound = max(
            max((clocks[j] for j in active), default=0),
            -(-total_work // max_busy),
        )
        if lower_bound > best_makespan:
            return

        pieces = piece_counts[i]
        tried = set()
        for j in range(m):
            # 当前时刻与机速都相同的机器互为对称：把本板给编号较小者
            # 所得序列恒字典序更小，只尝试其中一台。
            signature = (clocks[j], cut[j])
            if signature in tried:
                continue
            tried.add(signature)

            finish = clocks[j] + setup + pieces * cut[j]
            # 该机时刻只增不减，此子树工期必不小于 finish；严格大于当前
            # 最优时可剪，等于时保留（可能得到字典序更小的并列方案）。
            if finish > best_makespan:
                continue

            clocks[j] = finish
            assignment[i] = j
            dfs(i + 1)
            clocks[j] -= setup + pieces * cut[j]
            assignment[i] = -1

    dfs(0)
    return best_assignment, best_makespan


def _build_schedule(setup, machines, assignment, boards, makespan):
    """按分配结果整理每台机器的逐板开工/完工分钟。"""
    board_indices = [[] for _ in machines]
    for board_idx, machine_idx in enumerate(assignment):
        board_indices[machine_idx].append(board_idx)

    machine_results = []
    for j, (ready, cut) in enumerate(machines):
        clock = ready
        jobs = []
        for board_idx in board_indices[j]:
            pieces = boards[board_idx]["piece_count"]
            duration = setup + pieces * cut
            jobs.append(
                {
                    "board_no": board_idx + 1,
                    "piece_count": pieces,
                    "duration_minutes": duration,
                    "start_minutes": clock,
                    "finish_minutes": clock + duration,
                }
            )
            clock += duration

        machine_results.append(
            {
                "machine_no": j + 1,
                "ready_minutes": ready,
                "cut_minutes": cut,
                "job_count": len(jobs),
                "start_minutes": jobs[0]["start_minutes"] if jobs else None,
                "finish_minutes": jobs[-1]["finish_minutes"] if jobs else None,
                "jobs": jobs,
            }
        )

    return {
        "machine_count": len(machines),
        "setup_minutes": setup,
        "makespan": makespan,
        "machines": machine_results,
    }


def schedule(board_length, unit_price, available, parts, kerf, setup_minutes, machines):
    """单份清单排料后安排原板锯切作业。

    前五个参数与 ``optimizer.optimize`` 相同，另加：

    setup_minutes : int   统一的每板准备分钟（非负整数）
    machines      : list  2～4 台锯机，每项为
                          ``{"ready_minutes": 最早可用分钟（非负整数）,
                             "cut_minutes": 每件切割分钟（正整数）}``，
                          机台按录入顺序从 1 编号。

    返回
    ----
    dict
        可行时在 ``optimize`` 结果上附加 ``schedule``（逐机逐板开工/完工
        分钟与整体完工分钟；闲置机台不计入整体完工分钟）；排料无解时含
        ``feasible=False`` 与 ``reason``，不生成排程。

    抛出
    ----
    ValidationError
        输入不满足约束。
    """
    setup, machine_list = _validate_scheduling(setup_minutes, machines)

    result = optimize(board_length, unit_price, available, parts, kerf)
    if not result["feasible"]:
        # 排料无解：不生成排程。
        return result

    piece_counts = [board["piece_count"] for board in result["boards"]]
    ready = [machine[0] for machine in machine_list]
    cut = [machine[1] for machine in machine_list]
    assignment, makespan = _best_assignment(piece_counts, ready, cut, setup)
    result["schedule"] = _build_schedule(
        setup, machine_list, assignment, result["boards"], makespan
    )
    return result
