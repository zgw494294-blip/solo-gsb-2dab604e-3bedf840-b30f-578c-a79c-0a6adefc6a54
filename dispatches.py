"""跨批次合格切件发料单：一次性把 1～10 件已核销合格板的切件冻结发出。

``POST /api/dispatches`` 接收非空用途、非空幂等键与 1～10 件切件
（每件以 ``(batch_id, board_no, cut_no)`` 标识，可跨批次、不可重复）：

* 在单个 IMMEDIATE 事务里核对每件切件：批次存在、板属于该批次且已核销为
  「合格」、切件序号不越界、且尚未发料；任一件无效则整单不写入（400），
  切件已发料同样整单不写入（409）；
* 成功时冻结切件长度与归属（写入 ``dispatch_items``，主键即切件三元组，
  切件不得再次发料），生成持久化发料单；
* 同一幂等键、同一用途与同一选件集合（顺序不影响比较）的重试返回原单；
  同键异载荷返回 409。

``GET /api/dispatches/{id}`` 返回持久化的发料单明细。
"""

import contextlib
import json
import sqlite3

from batches import (
    STATUS_QUALIFIED,
    STATUS_SCRAPPED,
    ConflictError,
    _connect,
    _dumps,
    _transaction,
)
from optimizer import ValidationError

MIN_PIECES = 1
MAX_PIECES = 10


def _validate_dispatch(idem_key, purpose, pieces):
    """校验发料载荷，返回 (幂等键, 用途, 排序规范化后的选件列表)。"""
    if not isinstance(idem_key, str) or not idem_key.strip():
        raise ValidationError("幂等键必须为非空字符串")
    idem_key = idem_key.strip()
    if not isinstance(purpose, str) or not purpose.strip():
        raise ValidationError("用途必须为非空字符串")
    purpose = purpose.strip()

    if not isinstance(pieces, list) or not MIN_PIECES <= len(pieces) <= MAX_PIECES:
        raise ValidationError(f"选件列表须包含 {MIN_PIECES}～{MAX_PIECES} 件切件")

    normalized = []
    seen = set()
    for idx, row in enumerate(pieces, start=1):
        if not isinstance(row, dict):
            raise ValidationError(f"第 {idx} 件选件格式不正确")
        batch_id = row.get("batch_id")
        board_no = row.get("board_no")
        cut_no = row.get("cut_no")
        for value, label in (
            (batch_id, "批次 ID"),
            (board_no, "板号"),
            (cut_no, "切件序号"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValidationError(f"第 {idx} 件选件的{label}必须为正整数")
        cut_key = (batch_id, board_no, cut_no)
        if cut_key in seen:
            raise ValidationError(
                f"批次 {batch_id} 板号 {board_no} 切件 {cut_no} 在选件中重复"
            )
        seen.add(cut_key)
        normalized.append(
            {"batch_id": batch_id, "board_no": board_no, "cut_no": cut_no}
        )

    # 选件顺序不影响载荷比较：按（批次, 板号, 切件号）排序后规范化。
    normalized.sort(
        key=lambda item: (item["batch_id"], item["board_no"], item["cut_no"])
    )
    return idem_key, purpose, normalized


def create_dispatch(idem_key, purpose, pieces):
    """创建跨批次合格切件发料单。

    返回 ``(response, created)``：首次成功 ``created=True``（HTTP 201），
    同键同载荷幂等重试返回原单且 ``created=False``（HTTP 200）。

    抛出
    ----
    ValidationError
        载荷格式不合法（空幂等键/用途、选件数量越界、标识非正整数、
        选件重复、批次不存在、板不属于批次或非合格、切件序号越界）。
    ConflictError
        同键异载荷、选件中含已发料切件；整单不写入。
    """
    idem_key, purpose, normalized = _validate_dispatch(idem_key, purpose, pieces)
    payload_json = _dumps({"purpose": purpose, "pieces": normalized})

    with _transaction() as conn:
        # 幂等键检查先于选件核对：同键同载荷（用途与选件集合一致，顺序
        # 不影响）直接返回首次保存的发料单；同键异载荷冲突。
        saved = conn.execute(
            "SELECT payload_json, response_json FROM dispatches WHERE idem_key = ?",
            (idem_key,),
        ).fetchone()
        if saved is not None:
            if saved["payload_json"] == payload_json:
                return json.loads(saved["response_json"]), False
            raise ConflictError("幂等键已使用，且本次用途或选件集合与已保存发料单不一致")

        batch_ids = sorted({item["batch_id"] for item in normalized})
        placeholders = ",".join("?" * len(batch_ids))

        cuts_lookup = {}
        for batch_id in batch_ids:
            batch = conn.execute(
                "SELECT id, plan_json FROM batches WHERE id = ?",
                (batch_id,),
            ).fetchone()
            if batch is None:
                raise ValidationError(f"批次 {batch_id} 不存在")
            plan = json.loads(batch["plan_json"])
            for board in plan["boards"]:
                cuts_lookup[(batch_id, board["board_no"])] = board["cuts"]

        board_rows = conn.execute(
            f"SELECT batch_id, board_no, status FROM boards "
            f"WHERE batch_id IN ({placeholders})",
            batch_ids,
        ).fetchall()
        status_lookup = {
            (row["batch_id"], row["board_no"]): row["status"] for row in board_rows
        }

        dispatched_rows = conn.execute(
            f"SELECT batch_id, board_no, cut_no FROM dispatch_items "
            f"WHERE batch_id IN ({placeholders})",
            batch_ids,
        ).fetchall()
        dispatched = {
            (row["batch_id"], row["board_no"], row["cut_no"])
            for row in dispatched_rows
        }

        # 事务内核对分两遍，保证「载荷无效优先 400、仅已发料才 409」：
        # 第一遍核对板属本批次、已核销合格、切件序号不越界；
        # 第二遍核对全部选件尚未发料。任一件不满足则整单不写入。
        cuts_by_cut = {}
        for item in normalized:
            batch_id, board_no, cut_no = (
                item["batch_id"],
                item["board_no"],
                item["cut_no"],
            )
            board_key = (batch_id, board_no)
            if board_key not in status_lookup:
                raise ValidationError(f"板号 {board_no} 不属于批次 {batch_id}")
            status = status_lookup[board_key]
            if status != STATUS_QUALIFIED:
                label = "报废" if status == STATUS_SCRAPPED else "待加工"
                raise ValidationError(
                    f"批次 {batch_id} 的板号 {board_no} 当前为「{label}」，"
                    "仅合格板的切件可发料"
                )
            cuts = cuts_lookup[board_key]
            if cut_no > len(cuts):
                raise ValidationError(
                    f"批次 {batch_id} 的板号 {board_no} 只有 {len(cuts)} 个切件，"
                    f"切件序号 {cut_no} 越界"
                )
            cuts_by_cut[(batch_id, board_no, cut_no)] = cuts[cut_no - 1]

        for item in normalized:
            cut_key = (item["batch_id"], item["board_no"], item["cut_no"])
            if cut_key in dispatched:
                raise ConflictError(
                    f"批次 {item['batch_id']} 板号 {item['board_no']} "
                    f"切件 {item['cut_no']} 已发料，切件不得重复发料"
                )

        try:
            cursor = conn.execute(
                "INSERT INTO dispatches (idem_key, purpose, payload_json, response_json) "
                "VALUES (?, ?, ?, '')",
                (idem_key, purpose, payload_json),
            )
        except sqlite3.IntegrityError:
            # 并发请求抢用同一幂等键：让客户端重试取回已保存的发料单。
            raise ConflictError("幂等键已被并发请求使用，请重试以获取已保存的发料单")
        dispatch_id = cursor.lastrowid

        out_pieces = []
        total_length = 0
        for seq, item in enumerate(normalized, start=1):
            cut_key = (item["batch_id"], item["board_no"], item["cut_no"])
            length = cuts_by_cut[cut_key]
            total_length += length
            out_pieces.append(
                {
                    "batch_id": item["batch_id"],
                    "board_no": item["board_no"],
                    "cut_no": item["cut_no"],
                    "length": length,
                }
            )
            conn.execute(
                "INSERT INTO dispatch_items "
                "(dispatch_id, batch_id, board_no, cut_no, length, seq) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    dispatch_id,
                    item["batch_id"],
                    item["board_no"],
                    item["cut_no"],
                    length,
                    seq,
                ),
            )

        created_at = conn.execute(
            "SELECT created_at FROM dispatches WHERE id = ?",
            (dispatch_id,),
        ).fetchone()["created_at"]
        response = {
            "dispatch_id": dispatch_id,
            "idem_key": idem_key,
            "purpose": purpose,
            "piece_count": len(out_pieces),
            "total_length": total_length,
            "batch_count": len(batch_ids),
            "pieces": out_pieces,
            "created_at": created_at,
        }
        conn.execute(
            "UPDATE dispatches SET response_json = ? WHERE id = ?",
            (_dumps(response), dispatch_id),
        )
        return response, True


def get_dispatch(dispatch_id):
    """按 ID 读取持久化发料单明细；不存在时返回 None。"""
    with contextlib.closing(_connect()) as conn:
        row = conn.execute(
            "SELECT response_json FROM dispatches WHERE id = ?",
            (dispatch_id,),
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["response_json"])
