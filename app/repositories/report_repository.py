import uuid
from typing import List, Dict, Any, Tuple, Optional
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, status

from app.models.report_template import ReportTemplateModel
from app.services.catalog import ReportType, ReportField, FieldKind, FieldType, FilterOperator

class ReportRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_db_details(self, username: str, tenant_id: str) -> Dict[str, Any]:
        query = text("SELECT id, first_name, last_name FROM users WHERE username = :username AND tenant_id = :tenant_id")
        result = self.db.execute(query, {"username": username, "tenant_id": tenant_id}).fetchone()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario autenticado no existe en la base de datos de este inquilino"
            )
        return {
            "id": result[0],
            "first_name": result[1],
            "last_name": result[2],
            "full_name": f"{result[1]} {result[2]}"
        }

    def list_templates(self, tenant_id: str, owner_id: uuid.UUID) -> List[Any]:
        query = text("""
            SELECT t.*, (u.first_name || ' ' || u.last_name) as owner_name 
            FROM report_templates t
            JOIN users u ON u.id = t.owner_id
            WHERE t.tenant_id = :tenant_id AND (t.owner_id = :owner_id OR t.is_shared = true)
            ORDER BY t.updated_at DESC
        """)
        results = self.db.execute(query, {"tenant_id": tenant_id, "owner_id": owner_id}).fetchall()
        return results

    def create_template(self, model: ReportTemplateModel) -> ReportTemplateModel:
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def get_template_by_id(self, template_id: uuid.UUID, tenant_id: uuid.UUID) -> Optional[ReportTemplateModel]:
        return self.db.query(ReportTemplateModel).filter(
            ReportTemplateModel.id == template_id,
            ReportTemplateModel.tenant_id == tenant_id
        ).first()

    def update_template(self) -> None:
        self.db.commit()

    def delete_template(self, model: ReportTemplateModel) -> None:
        self.db.delete(model)
        self.db.commit()

    def execute_report_query(
        self,
        report_type: ReportType,
        tenant_id: str,
        selected_fields: List[str],
        filters: List[Any],
        sort_field: Optional[str] = None,
        sort_order: str = "asc",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[str], Dict[str, str], List[Dict[str, Any]], int, List[str]]:
        
        # Helper helpers locally
        def resolve_selected_fields(rt: ReportType, sf: List[str]) -> List[ReportField]:
            if rt.is_aggregated:
                dims = []
                for key in sf:
                    field = rt.fields.get(key)
                    if field and field.kind == FieldKind.DIMENSION:
                        dims.append(field)
                if not dims:
                    for field in rt.fields.values():
                        if field.kind == FieldKind.DIMENSION:
                            dims.append(field)
                measures = [f for f in rt.fields.values() if f.kind == FieldKind.MEASURE]
                return dims + measures
            out = []
            for key in sf:
                field = rt.fields.get(key)
                if field and field.kind == FieldKind.PLAIN:
                    out.append(field)
            if not out:
                out = [f for f in rt.fields.values() if f.kind == FieldKind.PLAIN]
            return out

        def build_comparator(field: ReportField, op: FilterOperator, pname: str) -> Optional[str]:
            tpl = op.sql_template().replace(":p", f":{pname}")
            if field.type == FieldType.NUMBER:
                return tpl.replace(f":{pname}", f"CAST(:{pname} AS numeric)")
            elif field.type == FieldType.DATE:
                if op == FilterOperator.LIKE:
                    return None
                return tpl.replace(f":{pname}", f"CAST(:{pname} AS date)")
            elif field.type == FieldType.BOOLEAN:
                if op in (FilterOperator.EQ, FilterOperator.NE):
                    return tpl.replace(f":{pname}", f"CAST(:{pname} AS boolean)")
                return None
            return tpl

        def coerce_value(field: ReportField, op: FilterOperator, raw_val: Any) -> Any:
            s = str(raw_val)
            if field.type == FieldType.NUMBER:
                return Decimal(s)
            elif field.type == FieldType.BOOLEAN:
                return s.lower() in ("true", "1", "yes")
            elif field.type == FieldType.STRING:
                if op == FilterOperator.LIKE:
                    return f"%{s}%"
                return s
            elif field.type == FieldType.DATE:
                return s
            return raw_val

        def describe_op(op: FilterOperator) -> str:
            desc = {
                FilterOperator.EQ: "=",
                FilterOperator.NE: "≠",
                FilterOperator.GT: ">",
                FilterOperator.LT: "<",
                FilterOperator.GTE: "≥",
                FilterOperator.LTE: "≤",
                FilterOperator.LIKE: "contiene",
                FilterOperator.IS_NULL: "es nulo",
                FilterOperator.IS_NOT_NULL: "no es nulo"
            }
            return desc.get(op, str(op.value))

        selected = resolve_selected_fields(report_type, selected_fields)

        needed_joins = set()
        for f in selected:
            needed_joins.update(f.joins)
        for flt in filters:
            # filters can be a list of Pydantic models or list of dicts
            f_key = flt.field if hasattr(flt, "field") else flt.get("field")
            f_field = report_type.fields.get(f_key)
            if f_field:
                needed_joins.update(f_field.joins)

        join_sql = ""
        for j_key in needed_joins:
            j_sql = report_type.joins.get(j_key)
            if j_sql:
                join_sql += f" {j_sql}"

        select_parts = []
        for i, field in enumerate(selected):
            select_parts.append(f"{field.sql} AS c{i}")

        where_clauses = [f"{report_type.tenant_column} = :p_tenant"]
        having_clauses = []
        params = {"p_tenant": tenant_id}
        applied_filters = []

        if report_type.date_field and date_from and date_from.strip():
            where_clauses.append(f"{report_type.date_field} >= CAST(:p_date_from AS date)")
            params["p_date_from"] = date_from.strip()
            applied_filters.append(f"Desde: {date_from}")

        if report_type.date_field and date_to and date_to.strip():
            where_clauses.append(f"{report_type.date_field} < (CAST(:p_date_to AS date) + INTERVAL '1 day')")
            params["p_date_to"] = date_to.strip()
            applied_filters.append(f"Hasta: {date_to}")

        for idx, flt in enumerate(filters):
            f_key = flt.field if hasattr(flt, "field") else flt.get("field")
            op_str = flt.operator if hasattr(flt, "operator") else flt.get("operator")
            val = flt.value if hasattr(flt, "value") else flt.get("value")

            field = report_type.fields.get(f_key)
            if not field or not op_str:
                continue

            try:
                op = FilterOperator(op_str)
            except ValueError:
                continue

            target_list = having_clauses if field.kind == FieldKind.MEASURE else where_clauses

            if not op.needs_value():
                target_list.append(f"{field.sql} {op.sql_template()}")
                applied_filters.append(f"{field.label} {describe_op(op)}")
                continue

            if val is None or (op.needs_value() and str(val).strip() == ""):
                continue

            pname = f"p_f{idx}"
            comparator = build_comparator(field, op, pname)
            if not comparator:
                continue

            target_list.append(f"{field.sql} {comparator}")
            params[pname] = coerce_value(field, op, val)
            applied_filters.append(f"{field.label} {describe_op(op)} {val}")

        group_by_sql = ""
        if report_type.is_aggregated:
            dims = [f.sql for f in selected if f.kind == FieldKind.DIMENSION]
            if dims:
                group_by_sql = f" GROUP BY {', '.join(dims)}"

        order_by_sql = ""
        if sort_field:
            sf = report_type.fields.get(sort_field)
            if sf and sf in selected:
                direction = "DESC" if sort_order.lower() == "desc" else "ASC"
                order_by_sql = f" ORDER BY {sf.sql} {direction}"

        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        having_sql = f" HAVING {' AND '.join(having_clauses)}" if having_clauses else ""

        base_from = f" FROM {report_type.from_clause}{join_sql}{where_sql}{group_by_sql}{having_sql}"

        sql_main = f"SELECT {', '.join(select_parts)}{base_from}{order_by_sql} LIMIT {limit} OFFSET {offset}"

        if report_type.is_aggregated:
            sql_count = f"SELECT COUNT(*) FROM (SELECT 1{base_from}) AS grp"
        else:
            sql_count = f"SELECT COUNT(*){base_from}"

        res = self.db.execute(text(sql_main), params).fetchall()
        
        rows = []
        columns = [f.key for f in selected]
        column_labels = {f.key: f.label for f in selected}

        for row in res:
            row_dict = {}
            for i, val in enumerate(row):
                if val is None:
                    row_dict[columns[i]] = ""
                elif isinstance(val, (int, float, Decimal)):
                    row_dict[columns[i]] = str(val)
                elif isinstance(val, bool):
                    row_dict[columns[i]] = "Sí" if val else "No"
                else:
                    row_dict[columns[i]] = str(val)
            rows.append(row_dict)

        total = self.db.execute(text(sql_count), params).scalar() or 0

        if not applied_filters:
            applied_filters.append("Sin filtros aplicados (SELECT *)")

        return columns, column_labels, rows, total, applied_filters
