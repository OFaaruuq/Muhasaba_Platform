"""Auto-recalculate KPIs when underlying data changes."""

import logging

from app.kpi.service import recalculate_student_kpis

logger = logging.getLogger(__name__)


def sync_kpis_for_student(student_id, period="term"):
    try:
        recalculate_student_kpis(student_id, period)
    except Exception:
        logger.exception(
            "KPI sync failed for student_id=%s period=%s",
            student_id,
            period,
        )
