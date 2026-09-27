"""木料定尺裁切 Web 应用 —— Flask 后端。

页面：GET /                            返回前端页面
接口：POST /api/solve                  接收 JSON 裁切需求，返回全局最优方案
     POST /api/allocate                接收多订单合板需求，返回 Shapley 费用分摊
     POST /api/schedule                接收单份清单与锯机参数，返回最优裁切与锯机排程
     POST /api/batches                 求解并冻结核销批次（无解不建批次）
     GET  /api/batches/{id}            返回批次快照、版本与逐板状态（含已发料切件）
     POST /api/batches/{id}/reports    幂等上报逐板核销结果，原子更新并递增版本
     POST /api/batches/{id}/quality-preview
                                       实测尺寸复核（只读，不修改批次）
     POST /api/batches/{id}/joint-preview
                                       合格切件错缝拼板预览（只读，不修改批次）
     POST /api/dispatches              跨批次合格切件发料单（一笔事务冻结，幂等）
     GET  /api/dispatches/{id}         返回持久化的发料单明细
"""

import os

from flask import Flask, jsonify, request, send_from_directory

from allocate import allocate
from batches import (
    ConflictError,
    NotFoundError,
    create_batch,
    get_batch,
    init_db,
    joint_preview,
    quality_preview,
    report_batch,
)
from dispatches import create_dispatch, get_dispatch
from optimizer import ValidationError, optimize
from schedule import schedule

app = Flask(__name__, static_folder="static", static_url_path="/static")

# 启动时自动初始化 SQLite（建目录、建表，幂等）。
init_db()


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/api/solve")
def solve():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "请求体必须为 JSON 对象"}), 400

    try:
        parts_raw = data.get("parts")
        if not isinstance(parts_raw, list):
            raise ValidationError("零件清单格式不正确")

        parts = []
        for row in parts_raw:
            if not isinstance(row, dict):
                raise ValidationError("零件清单格式不正确")
            parts.append((row.get("length"), row.get("quantity")))

        result = optimize(
            board_length=data.get("board_length"),
            unit_price=data.get("unit_price"),
            available=data.get("available"),
            parts=parts,
            kerf=data.get("kerf"),
        )
    except ValidationError as exc:
        # 输入约束错误：400，由前端标红提示。
        return jsonify({"error": str(exc)}), 400

    # 200 + feasible=False 表示“输入合法但不存在可行裁切方案”。
    return jsonify(result)


@app.post("/api/allocate")
def allocate_orders():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "请求体必须为 JSON 对象"}), 400

    try:
        orders_raw = data.get("orders")
        if not isinstance(orders_raw, list):
            raise ValidationError("订单列表格式不正确")

        orders = []
        for entry in orders_raw:
            if not isinstance(entry, dict):
                raise ValidationError("订单列表格式不正确")
            parts_raw = entry.get("parts")
            if not isinstance(parts_raw, list):
                raise ValidationError("订单零件清单格式不正确")
            parts = []
            for row in parts_raw:
                if not isinstance(row, dict):
                    raise ValidationError("订单零件清单格式不正确")
                parts.append((row.get("length"), row.get("quantity")))
            orders.append((entry.get("name"), parts))

        result = allocate(
            board_length=data.get("board_length"),
            unit_price=data.get("unit_price"),
            available=data.get("available"),
            kerf=data.get("kerf"),
            orders=orders,
        )
    except ValidationError as exc:
        # 输入约束错误：400，由前端标红提示。
        return jsonify({"error": str(exc)}), 400

    # 200 + feasible=False 表示“输入合法但全部订单合板无解”，不生成分摊。
    return jsonify(result)


@app.post("/api/schedule")
def schedule_boards():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "请求体必须为 JSON 对象"}), 400

    try:
        parts_raw = data.get("parts")
        if not isinstance(parts_raw, list):
            raise ValidationError("零件清单格式不正确")

        parts = []
        for row in parts_raw:
            if not isinstance(row, dict):
                raise ValidationError("零件清单格式不正确")
            parts.append((row.get("length"), row.get("quantity")))

        result = schedule(
            board_length=data.get("board_length"),
            unit_price=data.get("unit_price"),
            available=data.get("available"),
            parts=parts,
            kerf=data.get("kerf"),
            setup_minutes=data.get("setup_minutes"),
            machines=data.get("machines"),
        )
    except ValidationError as exc:
        # 输入约束错误：400，由前端标红提示。
        return jsonify({"error": str(exc)}), 400

    # 200 + feasible=False 表示“输入合法但不存在可行裁切方案”，不生成排程。
    return jsonify(result)


def _read_parts(data):
    """从请求 JSON 中读取零件清单，返回 [(长度, 件数), ...]。"""
    parts_raw = data.get("parts")
    if not isinstance(parts_raw, list):
        raise ValidationError("零件清单格式不正确")

    parts = []
    for row in parts_raw:
        if not isinstance(row, dict):
            raise ValidationError("零件清单格式不正确")
        parts.append((row.get("length"), row.get("quantity")))
    return parts


@app.post("/api/batches")
def create_cutting_batch():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "请求体必须为 JSON 对象"}), 400

    try:
        result = create_batch(
            board_length=data.get("board_length"),
            unit_price=data.get("unit_price"),
            available=data.get("available"),
            parts=_read_parts(data),
            kerf=data.get("kerf"),
        )
    except ValidationError as exc:
        # 输入约束错误：400，由前端标红提示。
        return jsonify({"error": str(exc)}), 400

    if not result["feasible"]:
        # 200 + feasible=False：输入合法但无解，不建批次。
        return jsonify(result)
    # 201：批次已冻结，版本 0，各板待加工。
    return jsonify(result), 201


@app.get("/api/batches/<int:batch_id>")
def fetch_batch(batch_id):
    batch = get_batch(batch_id)
    if batch is None:
        return jsonify({"error": f"批次 {batch_id} 不存在"}), 404
    return jsonify(batch)


@app.post("/api/batches/<int:batch_id>/reports")
def report_batch_results(batch_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "请求体必须为 JSON 对象"}), 400

    try:
        response = report_batch(
            batch_id=batch_id,
            idem_key=data.get("idem_key"),
            expected_version=data.get("expected_version"),
            results=data.get("results"),
        )
    except ValidationError as exc:
        # 载荷不合法（空幂等键、空结果、板号越界或重复等）：400。
        return jsonify({"error": str(exc)}), 400
    except NotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except ConflictError as exc:
        # 过期版本、已核销板、同键异载荷：409，整批不写入。
        return jsonify({"error": str(exc)}), 409

    # 成功或同键同载荷幂等重试：返回（保存的）响应。
    return jsonify(response)


@app.post("/api/batches/<int:batch_id>/quality-preview")
def preview_batch_quality(batch_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "请求体必须为 JSON 对象"}), 400

    try:
        response = quality_preview(
            batch_id=batch_id,
            tolerance=data.get("tolerance"),
            measurements=data.get("measurements"),
        )
    except ValidationError as exc:
        # 公差/实测记录非法、切件重复、板号不属于批次或非合格等：400。
        return jsonify({"error": str(exc)}), 400
    except NotFoundError as exc:
        return jsonify({"error": str(exc)}), 404

    # 只读预览：读取冻结需求与当前板状态，不修改批次。
    return jsonify(response)


@app.post("/api/batches/<int:batch_id>/joint-preview")
def preview_batch_joint(batch_id):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "请求体必须为 JSON 对象"}), 400

    try:
        response = joint_preview(
            batch_id=batch_id,
            pieces=data.get("pieces"),
            target_length=data.get("target_length"),
            row_count=data.get("row_count"),
            min_stagger=data.get("min_stagger"),
        )
    except ValidationError as exc:
        # 参数非法、选件重复、板号不属于批次或非合格、切件越界或已发料等：400。
        return jsonify({"error": str(exc)}), 400
    except NotFoundError as exc:
        return jsonify({"error": str(exc)}), 404

    # 只读预览：读取冻结切件长度与当前板状态，不修改批次与版本。
    return jsonify(response)


@app.post("/api/dispatches")
def create_dispatch_order():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "请求体必须为 JSON 对象"}), 400

    try:
        response, created = create_dispatch(
            idem_key=data.get("idem_key"),
            purpose=data.get("purpose"),
            pieces=data.get("pieces"),
        )
    except ValidationError as exc:
        # 载荷不合法（空幂等键/用途、选件数量越界、切件重复、批次不存在、
        # 板未核销合格、切件序号越界等）：400，整单不写入。
        return jsonify({"error": str(exc)}), 400
    except ConflictError as exc:
        # 同键异载荷、选件含已发料切件：409，整单不写入。
        return jsonify({"error": str(exc)}), 409

    # 201：新建发料单并冻结切件；200：同键同载荷幂等重试，返回原单。
    return jsonify(response), 201 if created else 200


@app.get("/api/dispatches/<int:dispatch_id>")
def fetch_dispatch(dispatch_id):
    dispatch = get_dispatch(dispatch_id)
    if dispatch is None:
        return jsonify({"error": f"发料单 {dispatch_id} 不存在"}), 404
    return jsonify(dispatch)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
