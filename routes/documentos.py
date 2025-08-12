# routes/documentos.py — Endpoints de documentos/códigos
from flask import Blueprint, request, jsonify
from db import get_conn
from pymysql.cursors import DictCursor

documentos_bp = Blueprint("documentos", __name__)

# --- GET /api/documentos ---
@documentos_bp.get("")
@documentos_bp.get("/")
def listar_documentos():
    conn = get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("""
                SELECT d.id, d.name, d.path,
                       GROUP_CONCAT(c.codigo ORDER BY c.codigo SEPARATOR ',') AS codigos
                FROM documentos d
                LEFT JOIN codigos c ON c.documento_id = d.id
                GROUP BY d.id, d.name, d.path
                ORDER BY d.id DESC
            """)
            rows = cur.fetchall()
        data = []
        for r in rows:
            codes = (r.get("codigos") or "")
            codes_list = [c for c in codes.split(",") if c] if codes else []
            data.append({
                "id": r["id"],
                "name": r["name"],
                "path": r["path"],
                "codigos": codes_list
            })
        return jsonify({"data": data})
    finally:
        conn.close()

# --- POST /api/documentos/search_by_code ---
# Alineado con el FRONT: body = { "codigo": "ABC", "modo": "prefijo"|"exacto" }
@documentos_bp.post("/search_by_code")
def search_by_code():
    body = request.get_json(silent=True) or {}
    codigo = (body.get("codigo") or "").strip().upper()
    modo = (body.get("modo") or "exacto").strip()

    if not codigo:
        return jsonify({"data": []})

    conn = get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            if modo == "prefijo":
                cur.execute("""
                    SELECT DISTINCT c.codigo
                    FROM codigos c
                    WHERE UPPER(c.codigo) LIKE %s
                    ORDER BY c.codigo
                    LIMIT 50
                """, (codigo + "%",))
                return jsonify({"data": [r["codigo"] for r in cur.fetchall()]})
            else:
                cur.execute("""
                    SELECT d.id, d.name, d.path
                    FROM documentos d
                    JOIN codigos c ON c.documento_id = d.id
                    WHERE UPPER(c.codigo) = %s
                """, (codigo,))
                docs = [{"id": r["id"], "name": r["name"], "path": r["path"]} for r in cur.fetchall()]
                return jsonify({"data": docs, "codigo": codigo})
    finally:
        conn.close()

# --- POST /api/documentos/search ---
# Recibe { texto } con códigos separados por coma/espacio/punto y coma/salto
@documentos_bp.post("/search")
def search_optima():
    body = request.get_json(silent=True) or {}
    texto = (body.get("texto") or "").strip()
    if not texto:
        return jsonify({"documentos": [], "codigos_faltantes": []})

    pedidos = [t.strip().upper() for t in
               texto.replace("\n", ",").replace("\r", ",").replace(";", ",").replace(" ", ",").split(",")
               if t.strip()]
    if not pedidos:
        return jsonify({"documentos": [], "codigos_faltantes": []})

    conn = get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute("""
                SELECT d.id, d.name, d.path, UPPER(c.codigo) AS codigo
                FROM documentos d
                JOIN codigos c ON c.documento_id = d.id
                WHERE UPPER(c.codigo) IN (%s)
            """ % ",".join(["%s"] * len(pedidos)), tuple(pedidos))
            rows = cur.fetchall()
    finally:
        conn.close()

    # Agrupar por documento
    docs_map = {}
    for r in rows:
        d = docs_map.setdefault(
            r["id"],
            {"documento": {"id": r["id"], "name": r["name"], "path": r["path"]}, "codigos_cubre": set()}
        )
        d["codigos_cubre"].add(r["codigo"])

    documentos = [{"documento": v["documento"], "codigos_cubre": sorted(list(v["codigos_cubre"]))}
                  for v in docs_map.values()]
    encontrados = {r["codigo"] for r in rows}
    faltantes = sorted(list(set(pedidos) - encontrados))
    return jsonify({"documentos": documentos, "codigos_faltantes": faltantes})
