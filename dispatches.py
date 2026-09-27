"""跨批次合格切件发料单：一笔事务冻结发料，幂等持久化。

``POST /api/dispatches`` 收集非空用途、非空幂等键与 1～10 件以
（批次 ID, 板号, 切件序号）标识的切件（可跨批次），在单个 IMMEDIATE
事务中核对并冻结：

* 每件切件所属批次存在、板已核销为「合格」、切件序号不越界，且选件
  在单内不重复；任一件无效整单不写入（HTTP 400）；
* 每件切件尚未出现在任何发料单中；任一件已发料整单不写入（HTTP 409）；
* 全部有效时把切件长度与归属（批次/板号/切件序号）随发料单一并冻结到
  SQLite，该切件此后不得再发料（``dispatch_items`` 主键兜底）。

幂等：同一幂等键、同一用途与同一选件集合的重试直接返回首次保存的发料单
（选件顺序不影响比较，按批次/板号/切件序号排序后规范化）；同键异载荷
视为冲突（HTTP 409）。

``GET /api/dispatches/{id}`` 返回持久化的发料单明细。
"""

import contextlib
import json

from batches import (
    STATUS_QUALIFIED,
    STATUS_SCRAPPED,
    ConflictError,
    _as_positive_int,
    _connect,
    _dumps,
    _transaction,
)
from optimizer import ValidationError


def _validate_dispatch(idem_key, purpose, pieces):
    """校验发料载荷，返回按 (批次, 板号, 切件号) 排序的规范化选件列表。"""
    if not isinstance(idem_key, str) or not idem_key.strip():
        raise ValidationError("幂等键必须为非空字符串")
    if not isinstance(purpose, str) or not purpose.strip():
        raise ValidationError("用途必须为非空字符串")
    if not isinstance(pieces, list) or not 1 <= len(pieces) <= 10:
        raise ValidationError("选件列表须包含 1～10 件切件")

    normalized = []
    seen = set()
    for idx, row in enumerate(pieces, start=1):
        if not isinstance(row, dict):
            raise ValidationError(f"第 {idx} 件选件格式不正确")
        batch_id = _as_positive_int(row.get("batch_id"), f"第 {idx} 件选件的批次 ID")
        board_no = _as_positive_int(row.get("board_no"), f"第 {idx} 件选件的板号")
        cut_no = _as_positive_int(row.get("cut_no"), f"第 {idx} 件选件的切件序号")
        cut_key = (batch_id, board_no, cut_no)
        if cut_key in seen:
            raise ValidationError(
                f"批次 {batch_id} 板号 {board_no} 切件 {cut_no} 的选件重复"
            )
        seen.add(cut_key)
        normalized.append(
            {"batch_id": batch_id, "board_no": board_no, "cut_no": cut_no}
        )

    # 选件顺序不影响载荷比较：排序后规范化。
    normalized.sort(
        key=lambda item: (item["batch_id"], item["board_no"], item["cut_no"])
    )
    return normalized


def create_dispatch(idem_key, purpose, pieces):
    """冻结一批跨批次合格切件为发料单。

    返回 ``(响应 dict, 是否新建)``：新建为 ``True``（HTTP 201）；同键同载荷
    幂等重试为 ``False``（HTTP 200，返回首次保存的发料单）。

    抛出
    ----
    ValidationError
        载荷不合法（空幂等键/用途、选件数量越界、切件重复、批次不存在、
        板号不属于批次或未核销合格、切件序号越界等）；整单不写入。
    ConflictError
        同键异载荷，或选件中已有切件被发料；整单不写入。
    """
    normalized = _validate_dispatch(idem_key, purpose, pieces)
    payload_json = _dumps({"purpose": purpose, "pieces": normalized})

    with _transaction() as conn:
        # 幂等键先于业务校验：同键同载荷的重试直接返回首次保存的发料单，
        # 即使其中的切件已被（首次请求）发料；同键异载荷冲突。
        saved = conn.execute(
            "SELECT payload_json, response_json FROM dispatches WHERE idem_key = ?",
            (idem_key,),
        ).fetchone()
        if saved is not None:
            if saved["payload_json"] == payload_json:
                return json.loads(saved["response_json"]), False
            raise ConflictError("幂等键已使用，且本次载荷与已保存载荷不一致")

        # 逐件核对：批次存在、板号属于批次且已核销合格、切件序号不越界；
        # 同时从冻结方案取出切件长度（随发料单一并冻结）。
        batch_info = {}
        for item in normalized:
            batch_id = item["batch_id"]
            if batch_id not in batch_info:
                batch = conn.execute(
                    "SELECT plan_json FROM batches WHERE id = ?", (batch_id,)
                ).fetchone()
                if batch is None:
                    raise ValidationError(f"批次 {batch_id} 不存在")
                plan = json.loads(batch["plan_json"])
                rows = conn.execute(
                    "SELECT board_no, status FROM boards WHERE batch_id = ?",
                    (batch_id,),
                ).fetchall()
                batch_info[batch_id] = {
                    "status": {row["board_no"]: row["status"] for row in rows},
                    "cut_count": {
                        board["board_no"]: len(board["cuts"])
                        for board in plan["boards"]
                    },
                    "cut_length": {
                        (board["board_no"], cut_idx + 1): cut_length
                        for board in plan["boards"]
                        for cut_idx, cut_length in enumerate(board["cuts"])
                    },
                }

            info = batch_info[batch_id]
            board_no = item["board_no"]
            if board_no not in info["status"]:
                raise ValidationError(f"板号 {board_no} 不属于批次 {batch_id}")
            status = info["status"][board_no]
            if status != STATUS_QUALIFIED:
                label = "报废" if status == STATUS_SCRAPPED else "待加工"
                raise ValidationError(
                    f"批次 {batch_id} 板号 {board_no} 当前为「{label}」，"
                    "仅合格板的切件可发料"
                )
            if item["cut_no"] > info["cut_count"][board_no]:
                raise ValidationError(
                    f"批次 {batch_id} 板号 {board_no} 只有 "
                    f"{info['cut_count'][board_no]} 个切件，"
                    f"切件序号 {item['cut_no']} 越界"
                )
            item["length"] = info["cut_length"][(board_no, item["cut_no"])]

        # 已发料核对：任一件已发料整单不写入（409）。
        for item in normalized:
            used = conn.execute(
                "SELECT dispatch_id FROM dispatch_items "
                "WHERE batch_id = ? AND board_no = ? AND cut_no = ?",
                (item["batch_id"], item["board_no"], item["cut_no"]),
            ).fetchone()
            if used is not None:
                raise ConflictError(
                    f"批次 {item['batch_id']} 板号 {item['board_no']} "
                    f"切件 {item['cut_no']} 已发料"
                    f"（发料单 #{used['dispatch_id']}），整单不写入"
                )

        # 原子写入：发料单 + 逐件冻结（长度与归属）+ 保存响应。
        cursor = conn.execute(
            "INSERT INTO dispatches (idem_key, purpose, payload_json, response_json) "
            "VALUES (?, ?, ?, ?)",
            (idem_key, purpose, payload_json, ""),
        )
        dispatch_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO dispatch_items "
            "(dispatch_id, batch_id, board_no, cut_no, length) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    dispatch_id,
                    item["batch_id"],
                    item["board_no"],
                    item["cut_no"],
                    item["length"],
                )
                for item in normalized
            ],
        )
        created_at = conn.execute(
            "SELECT created_at FROM dispatches WHERE id = ?", (dispatch_id,)
        ).fetchone()["created_at"]
        response = {
            "dispatch_id": dispatch_id,
            "idem_key": idem_key,
            "purpose": purpose,
            "piece_count": len(normalized),
            "created_at": created_at,
            "pieces": [
                {
                    "batch_id": item["batch_id"],
                    "board_no": item["board_no"],
                    "cut_no": item["cut_no"],
                    "length": item["length"],
                }
                for item in normalized
            ],
        }
        conn.execute(
            "UPDATE dispatches SET response_json = ? WHERE id = ?",
            (_dumps(response), dispatch_id),
        )
        return response, True


def get_dispatch(dispatch_id):
    """按 ID 读取持久化的发料单明细；不存在时返回 None。"""
    with contextlib.closing(_connect()) as conn:
        row = conn.execute(
            "SELECT response_json FROM dispatches WHERE id = ?", (dispatch_id,)
        ).fetchone()
    if row is None:
        return None
    return json.loads(row["response_json"])
