"""裁切执行核销批次：方案冻结、逐板核销与幂等上报。

``POST /api/batches`` 用单份清单参数在服务端求解，可行时把输入与逐板方案
冻结到 SQLite：批次版本从 0 开始，各板初始状态为「待加工」；无解不建批次。

``POST /api/batches/{id}/reports`` 接收非空幂等键、期望版本与非空逐板结果，
每板仅可从「待加工」转为「合格」或「报废」：

* 同批次同键同载荷的重试直接返回首次保存的响应，不再校验期望版本
  （忽略旧版本）；结果列表的顺序不影响载荷比较（按板号排序后规范化）；
* 同键异载荷、期望版本过期、上报已核销板均视为冲突（HTTP 409），
  整批不写入；
* 成功时在单个 IMMEDIATE 事务里原子更新所有板、批次版本加一，
  并把本次响应随上报记录一并保存。
"""

import contextlib
import json
import os
import sqlite3

from joint import plan_joint
from optimizer import ValidationError, optimize
from quality import expand_demands, match_measurements

# 数据库文件路径：默认放在应用目录下的 data/（Docker 中挂载持久卷），
# 可用环境变量 DB_PATH 覆盖。
DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "batches.db"),
)

STATUS_PENDING = "pending"        # 待加工
STATUS_QUALIFIED = "qualified"    # 合格
STATUS_SCRAPPED = "scrapped"      # 报废
REPORT_RESULTS = (STATUS_QUALIFIED, STATUS_SCRAPPED)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL DEFAULT 0,
    input_json TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS boards (
    batch_id INTEGER NOT NULL REFERENCES batches (id),
    board_no INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    PRIMARY KEY (batch_id, board_no)
);
CREATE TABLE IF NOT EXISTS reports (
    batch_id INTEGER NOT NULL REFERENCES batches (id),
    idem_key TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (batch_id, idem_key)
);
-- 跨批次合格切件发料单：idem_key 全局唯一；dispatch_items 主键保证
-- 同一切件（批次, 板号, 切件序号）至多出现在一张发料单中（不得再发料）。
CREATE TABLE IF NOT EXISTS dispatches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    idem_key TEXT NOT NULL UNIQUE,
    purpose TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS dispatch_items (
    batch_id INTEGER NOT NULL REFERENCES batches (id),
    board_no INTEGER NOT NULL,
    cut_no INTEGER NOT NULL,
    length INTEGER NOT NULL,
    dispatch_id INTEGER NOT NULL REFERENCES dispatches (id),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (batch_id, board_no, cut_no)
);
"""


class ConflictError(Exception):
    """上报与批次当前状态冲突（过期版本、已核销板、同键异载荷）。"""


class NotFoundError(Exception):
    """批次不存在。"""


def _connect():
    # autocommit 模式：事务由代码显式 BEGIN/COMMIT/ROLLBACK 控制；
    # busy_timeout 让并发写请求排队等待而不是立即报 SQLITE_BUSY。
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextlib.contextmanager
def _transaction():
    """IMMEDIATE 事务：进入即取写锁，提交或回滚后关闭连接。"""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def init_db():
    """创建数据库目录并初始化表结构（幂等，应用启动时调用一次）。"""
    directory = os.path.dirname(DB_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with contextlib.closing(_connect()) as conn:
        conn.executescript(_SCHEMA)
        # WAL 允许读写并发；该模式是数据库的持久属性，只需设置一次。
        conn.execute("PRAGMA journal_mode = WAL")


def _dumps(obj):
    return json.dumps(obj, ensure_ascii=False)


def _boards_with_status(plan_boards, status_by_no, dispatched_by_no=None):
    """把冻结方案中的逐板数据与当前核销状态、已发料切件合并。"""
    boards = []
    for board in plan_boards:
        merged = dict(board)
        merged["status"] = status_by_no[board["board_no"]]
        merged["dispatched_cuts"] = (
            dispatched_by_no.get(board["board_no"], []) if dispatched_by_no else []
        )
        boards.append(merged)
    return boards


def _dispatched_cuts(conn, batch_id):
    """批次内已发料切件：{板号: [切件序号, ...]}（各自升序）。"""
    rows = conn.execute(
        "SELECT board_no, cut_no FROM dispatch_items WHERE batch_id = ? "
        "ORDER BY board_no, cut_no",
        (batch_id,),
    ).fetchall()
    cuts_by_board = {}
    for row in rows:
        cuts_by_board.setdefault(row["board_no"], []).append(row["cut_no"])
    return cuts_by_board


def create_batch(board_length, unit_price, available, parts, kerf):
    """求解单份清单，可行时冻结为核销批次。

    参数与 ``optimizer.optimize`` 相同。返回 optimize 风格结果：
    可行时附加 ``batch_id``、``version``（恒为 0）、冻结的 ``input``，
    且每块板带 ``status='pending'``；无解时不建批次，原样返回无解信息。

    抛出
    ----
    ValidationError
        输入不满足约束。
    """
    result = optimize(board_length, unit_price, available, parts, kerf)
    if not result["feasible"]:
        # 无解：不建批次。
        return result

    frozen_input = {
        "board_length": board_length,
        "unit_price": unit_price,
        "available": available,
        "kerf": kerf,
        "parts": [
            {"length": length, "quantity": quantity} for length, quantity in parts
        ],
    }
    plan = {"boards": result["boards"], "summary": result["summary"]}

    with _transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO batches (input_json, plan_json) VALUES (?, ?)",
            (_dumps(frozen_input), _dumps(plan)),
        )
        batch_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO boards (batch_id, board_no) VALUES (?, ?)",
            [(batch_id, board["board_no"]) for board in result["boards"]],
        )

    result["batch_id"] = batch_id
    result["version"] = 0
    result["input"] = frozen_input
    for board in result["boards"]:
        board["status"] = STATUS_PENDING
        board["dispatched_cuts"] = []
    return result


def get_batch(batch_id):
    """按 ID 读取批次快照、版本、逐板状态与已发料切件；不存在时返回 None。"""
    with contextlib.closing(_connect()) as conn:
        batch = conn.execute(
            "SELECT id, version, input_json, plan_json FROM batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        if batch is None:
            return None
        rows = conn.execute(
            "SELECT board_no, status FROM boards WHERE batch_id = ?",
            (batch_id,),
        ).fetchall()
        dispatched_by_no = _dispatched_cuts(conn, batch_id)

    plan = json.loads(batch["plan_json"])
    status_by_no = {row["board_no"]: row["status"] for row in rows}
    return {
        "batch_id": batch["id"],
        "version": batch["version"],
        "input": json.loads(batch["input_json"]),
        "boards": _boards_with_status(plan["boards"], status_by_no, dispatched_by_no),
        "summary": plan["summary"],
    }


def _validate_report(idem_key, expected_version, results):
    """校验上报载荷，返回按板号排序的规范化逐板结果列表。"""
    if not isinstance(idem_key, str) or not idem_key.strip():
        raise ValidationError("幂等键必须为非空字符串")
    if (
        isinstance(expected_version, bool)
        or not isinstance(expected_version, int)
        or expected_version < 0
    ):
        raise ValidationError("期望版本必须为非负整数")
    if not isinstance(results, list) or len(results) == 0:
        raise ValidationError("逐板结果不能为空")

    normalized = []
    seen = set()
    for idx, row in enumerate(results, start=1):
        if not isinstance(row, dict):
            raise ValidationError(f"第 {idx} 条结果格式不正确")
        board_no = row.get("board_no")
        if isinstance(board_no, bool) or not isinstance(board_no, int):
            raise ValidationError(f"第 {idx} 条结果的板号必须为整数")
        result = row.get("result")
        if result not in REPORT_RESULTS:
            raise ValidationError(
                f"第 {idx} 条结果必须为「{STATUS_QUALIFIED}」或「{STATUS_SCRAPPED}」"
            )
        if board_no in seen:
            raise ValidationError(f"板号 {board_no} 在结果中重复")
        seen.add(board_no)
        normalized.append({"board_no": board_no, "result": result})

    # 结果列表顺序不影响载荷比较：按板号排序后规范化。
    normalized.sort(key=lambda item: item["board_no"])
    return normalized


def report_batch(batch_id, idem_key, expected_version, results):
    """对批次提交逐板核销结果。

    成功（或同键同载荷幂等重试）时返回响应 dict，含新的 ``version``、
    本次更新的 ``updated`` 列表与批次最新快照。

    抛出
    ----
    ValidationError
        载荷格式不合法（空幂等键、空结果、板号不属于批次、板号重复等）。
    NotFoundError
        批次不存在。
    ConflictError
        同键异载荷、期望版本过期或上报已核销板；整批不写入。
    """
    normalized = _validate_report(idem_key, expected_version, results)
    payload_json = _dumps(normalized)

    with _transaction() as conn:
        batch = conn.execute(
            "SELECT id, version, input_json, plan_json FROM batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        if batch is None:
            raise NotFoundError(f"批次 {batch_id} 不存在")

        # 幂等键先于版本检查：同批次同键同载荷的重试直接返回首次保存的
        # 响应，忽略旧版本；同键异载荷冲突。
        saved = conn.execute(
            "SELECT payload_json, response_json FROM reports "
            "WHERE batch_id = ? AND idem_key = ?",
            (batch_id, idem_key),
        ).fetchone()
        if saved is not None:
            if saved["payload_json"] == payload_json:
                return json.loads(saved["response_json"])
            raise ConflictError("幂等键已使用，且本次载荷与已保存载荷不一致")

        rows = conn.execute(
            "SELECT board_no, status FROM boards WHERE batch_id = ?",
            (batch_id,),
        ).fetchall()
        status_by_no = {row["board_no"]: row["status"] for row in rows}

        for item in normalized:
            if item["board_no"] not in status_by_no:
                raise ValidationError(
                    f"板号 {item['board_no']} 不属于批次 {batch_id}"
                )

        if expected_version != batch["version"]:
            raise ConflictError(
                f"期望版本 {expected_version} 与当前版本 {batch['version']} 不一致"
            )

        for item in normalized:
            if status_by_no[item["board_no"]] != STATUS_PENDING:
                raise ConflictError(
                    f"板号 {item['board_no']} 已核销，不能重复上报"
                )

        # 原子写入：更新所有板、版本加一、保存上报记录与响应。
        new_version = batch["version"] + 1
        conn.executemany(
            "UPDATE boards SET status = ? WHERE batch_id = ? AND board_no = ?",
            [
                (item["result"], batch_id, item["board_no"])
                for item in normalized
            ],
        )
        conn.execute(
            "UPDATE batches SET version = ? WHERE id = ?", (new_version, batch_id)
        )

        plan = json.loads(batch["plan_json"])
        for item in normalized:
            status_by_no[item["board_no"]] = item["result"]
        response = {
            "batch_id": batch_id,
            "version": new_version,
            "updated": [
                {"board_no": item["board_no"], "status": item["result"]}
                for item in normalized
            ],
            "input": json.loads(batch["input_json"]),
            "boards": _boards_with_status(
                plan["boards"], status_by_no, _dispatched_cuts(conn, batch_id)
            ),
            "summary": plan["summary"],
        }
        conn.execute(
            "INSERT INTO reports (batch_id, idem_key, payload_json, response_json) "
            "VALUES (?, ?, ?, ?)",
            (batch_id, idem_key, payload_json, _dumps(response)),
        )
        return response


def _as_nonneg_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{name}必须为整数")
    if value < 0:
        raise ValidationError(f"{name}必须为非负整数")
    return value


def _as_positive_int(value, name):
    value = _as_nonneg_int(value, name)
    if value <= 0:
        raise ValidationError(f"{name}必须为正整数")
    return value


def quality_preview(batch_id, tolerance, measurements):
    """批次实测尺寸复核（只读预览，不修改批次）。

    读取冻结需求与当前逐板状态，把已录入实测件按最优方式匹配给冻结需求件：
    仅接受「合格」板上的切件记录，重复切件、待加工或报废板的记录一律拒绝；
    未录入的切件不参与本次复核。匹配规则见 ``quality.match_measurements``。

    抛出
    ----
    ValidationError
        公差非法、测量记录格式非法、切件重复、板号不属于批次或该板非合格、
        切件序号越界等。
    NotFoundError
        批次不存在。
    """
    tolerance = _as_nonneg_int(tolerance, "公差")

    if not isinstance(measurements, list):
        raise ValidationError("实测记录必须为列表")

    normalized = []
    seen_cuts = set()
    for idx, row in enumerate(measurements, start=1):
        if not isinstance(row, dict):
            raise ValidationError(f"第 {idx} 条实测记录格式不正确")
        board_no = _as_positive_int(row.get("board_no"), f"第 {idx} 条实测记录的板号")
        cut_no = _as_positive_int(row.get("cut_no"), f"第 {idx} 条实测记录的切件序号")
        actual_length = _as_positive_int(
            row.get("actual_length"), f"第 {idx} 条实测记录的实测长度"
        )
        cut_key = (board_no, cut_no)
        if cut_key in seen_cuts:
            raise ValidationError(
                f"板号 {board_no} 切件 {cut_no} 的实测记录重复"
            )
        seen_cuts.add(cut_key)
        normalized.append(
            {
                "board_no": board_no,
                "cut_no": cut_no,
                "actual_length": actual_length,
            }
        )

    with contextlib.closing(_connect()) as conn:
        batch = conn.execute(
            "SELECT id, input_json, plan_json FROM batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        if batch is None:
            raise NotFoundError(f"批次 {batch_id} 不存在")

        rows = conn.execute(
            "SELECT board_no, status FROM boards WHERE batch_id = ?",
            (batch_id,),
        ).fetchall()
        status_by_no = {row["board_no"]: row["status"] for row in rows}

    frozen_input = json.loads(batch["input_json"])
    plan = json.loads(batch["plan_json"])

    cut_count_by_no = {
        board["board_no"]: len(board["cuts"]) for board in plan["boards"]
    }
    cut_length_lookup = {
        (board["board_no"], cut_idx + 1): cut_length
        for board in plan["boards"]
        for cut_idx, cut_length in enumerate(board["cuts"])
    }

    for item in normalized:
        board_no = item["board_no"]
        if board_no not in status_by_no:
            raise ValidationError(f"板号 {board_no} 不属于批次 {batch_id}")
        status = status_by_no[board_no]
        if status != STATUS_QUALIFIED:
            label = "报废" if status == STATUS_SCRAPPED else "待加工"
            raise ValidationError(
                f"板号 {board_no} 当前为「{label}」，仅合格板的切件可录入实测尺寸"
            )
        if item["cut_no"] > cut_count_by_no[board_no]:
            raise ValidationError(
                f"板号 {board_no} 只有 {cut_count_by_no[board_no]} 个切件，"
                f"切件序号 {item['cut_no']} 越界"
            )
        item["planned_length"] = cut_length_lookup[(board_no, item["cut_no"])]

    # 冻结需求按录入顺序展开为单件（序号从 1 开始）。
    demands = expand_demands(frozen_input["parts"])
    result = match_measurements(demands, normalized, tolerance)

    matched_by_length = {}
    for item in result["assignments"]:
        if item["assigned"]:
            matched_by_length[item["demand_length"]] = (
                matched_by_length.get(item["demand_length"], 0) + 1
            )

    # 各需求长度的缺件数 = 冻结需求件数 − 分给该长度的实测件数。
    shortages = [
        {
            "length": row["length"],
            "required": row["quantity"],
            "matched": matched_by_length.get(row["length"], 0),
            "shortage": row["quantity"] - matched_by_length.get(row["length"], 0),
        }
        for row in frozen_input["parts"]
    ]

    return {
        "batch_id": batch_id,
        "tolerance": tolerance,
        "demand_count": len(demands),
        "measured_count": len(normalized),
        "matched_count": result["matched_count"],
        "unassigned_count": len(normalized) - result["matched_count"],
        "total_deviation": result["total_deviation"],
        "demands": [
            {"demand_no": seq, "length": length} for seq, length in demands
        ],
        "assignments": result["assignments"],
        "unassigned": [
            item for item in result["assignments"] if not item["assigned"]
        ],
        "shortages": shortages,
    }


def joint_preview(batch_id, pieces, target_length, row_count, min_stagger):
    """合格切件错缝拼板预览（只读，不修改批次与版本）。

    校验选件（1～10 件、(板号, 切件号) 标识、无重复、板属于批次且仍合格、
    切件序号不越界、未发料），读取冻结切件长度后调用 ``joint.plan_joint``
    精确求解错缝拼板排布；无解时返回 ``feasible=False`` 与原因。

    抛出
    ----
    ValidationError
        参数非法、选件重复、板号不属于批次或该板非合格、切件序号越界、
        切件已发料等。
    NotFoundError
        批次不存在。
    """
    target_length = _as_positive_int(target_length, "目标行长")
    if isinstance(row_count, bool) or not isinstance(row_count, int):
        raise ValidationError("行数必须为整数")
    if not 2 <= row_count <= 4:
        raise ValidationError("行数必须为 2～4 的整数")
    min_stagger = _as_nonneg_int(min_stagger, "最小错缝距离")

    if not isinstance(pieces, list) or not 1 <= len(pieces) <= 10:
        raise ValidationError("选件列表须包含 1～10 件切件")

    normalized = []
    seen_cuts = set()
    for idx, row in enumerate(pieces, start=1):
        if not isinstance(row, dict):
            raise ValidationError(f"第 {idx} 件选件格式不正确")
        board_no = _as_positive_int(row.get("board_no"), f"第 {idx} 件选件的板号")
        cut_no = _as_positive_int(row.get("cut_no"), f"第 {idx} 件选件的切件序号")
        cut_key = (board_no, cut_no)
        if cut_key in seen_cuts:
            raise ValidationError(f"板号 {board_no} 切件 {cut_no} 的选件重复")
        seen_cuts.add(cut_key)
        normalized.append({"board_no": board_no, "cut_no": cut_no})

    with contextlib.closing(_connect()) as conn:
        batch = conn.execute(
            "SELECT id, plan_json FROM batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        if batch is None:
            raise NotFoundError(f"批次 {batch_id} 不存在")

        rows = conn.execute(
            "SELECT board_no, status FROM boards WHERE batch_id = ?",
            (batch_id,),
        ).fetchall()
        status_by_no = {row["board_no"]: row["status"] for row in rows}

        dispatched_rows = conn.execute(
            "SELECT board_no, cut_no FROM dispatch_items WHERE batch_id = ?",
            (batch_id,),
        ).fetchall()
        dispatched = {(row["board_no"], row["cut_no"]) for row in dispatched_rows}

    plan = json.loads(batch["plan_json"])

    cut_count_by_no = {
        board["board_no"]: len(board["cuts"]) for board in plan["boards"]
    }
    cut_length_lookup = {
        (board["board_no"], cut_idx + 1): cut_length
        for board in plan["boards"]
        for cut_idx, cut_length in enumerate(board["cuts"])
    }

    for item in normalized:
        board_no = item["board_no"]
        if board_no not in status_by_no:
            raise ValidationError(f"板号 {board_no} 不属于批次 {batch_id}")
        status = status_by_no[board_no]
        if status != STATUS_QUALIFIED:
            label = "报废" if status == STATUS_SCRAPPED else "待加工"
            raise ValidationError(
                f"板号 {board_no} 当前为「{label}」，仅合格板的切件可参与拼板"
            )
        if item["cut_no"] > cut_count_by_no[board_no]:
            raise ValidationError(
                f"板号 {board_no} 只有 {cut_count_by_no[board_no]} 个切件，"
                f"切件序号 {item['cut_no']} 越界"
            )
        if (board_no, item["cut_no"]) in dispatched:
            raise ValidationError(
                f"板号 {board_no} 切件 {item['cut_no']} 已发料，不能参与拼板"
            )
        # 切件长度取批次冻结值。
        item["length"] = cut_length_lookup[(board_no, item["cut_no"])]

    result = plan_joint(normalized, target_length, row_count, min_stagger)

    response = {
        "batch_id": batch_id,
        "feasible": result["feasible"],
        "target_length": target_length,
        "row_count": row_count,
        "min_stagger": min_stagger,
        "selected_count": len(normalized),
    }
    if not result["feasible"]:
        response["reason"] = result["reason"]
        return response

    response.update(
        {
            "used_count": result["used_count"],
            "unused_count": len(normalized) - result["used_count"],
            "rows": result["rows"],
            "unused": result["unused"],
        }
    )
    return response
