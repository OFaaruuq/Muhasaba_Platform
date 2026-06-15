"""Admin CRUD for KPI indicators and related config (dynamic, DB-driven)."""

from app.extensions import db
from app.models import KPI, StudentKPI
from app.services.config_service import get_kpi_source_options


def kpi_query_for_school(school_id, active_only=False):
    query = KPI.query
    if school_id:
        query = query.filter((KPI.school_id == school_id) | (KPI.school_id.is_(None)))
    else:
        query = query.filter(KPI.school_id.is_(None))
    if active_only:
        query = query.filter_by(is_active=True)
    return query.order_by(KPI.is_active.desc(), KPI.weight.desc(), KPI.name_ar)


def total_active_kpi_weight(kpis):
    return round(sum(k.weight for k in kpis if k.is_active), 1)


def add_kpi_for_school(school_id, form):
    code = (form.get("code") or "").strip()
    if not code:
        code = form.get("name", "").lower().replace(" ", "_").strip()
    if not code:
        raise ValueError("رمز مصدر البيانات مطلوب.")

    existing = KPI.query.filter_by(code=code)
    if school_id:
        existing = existing.filter(
            (KPI.school_id == school_id) | (KPI.school_id.is_(None))
        )
    else:
        existing = existing.filter(KPI.school_id.is_(None))
    if existing.first():
        raise ValueError("مؤشر بنفس الرمز موجود.")

    kpi = KPI(
        code=code,
        name=form.get("name") or form.get("name_ar") or form["name_ar"],
        name_ar=form["name_ar"],
        weight=float(form.get("weight", 10)),
        description=(form.get("description") or "").strip() or None,
        school_id=school_id,
        is_active=True,
    )
    db.session.add(kpi)
    return kpi


def update_kpi_from_form(kpi, form):
    kpi.name_ar = form.get("name_ar", kpi.name_ar)
    if form.get("name"):
        kpi.name = form.get("name")
    if form.get("weight") is not None:
        kpi.weight = float(form.get("weight", kpi.weight))
    if "description" in form:
        kpi.description = (form.get("description") or "").strip() or None
    if form.get("code") and form.get("code") != kpi.code:
        dup = KPI.query.filter_by(code=form.get("code"), school_id=kpi.school_id).first()
        if dup and dup.id != kpi.id:
            raise ValueError("رمز المؤشر مستخدم.")
        kpi.code = form.get("code").strip()
    return kpi


def toggle_kpi(kpi_id):
    kpi = KPI.query.get(kpi_id)
    if not kpi:
        raise ValueError("المؤشر غير موجود.")
    kpi.is_active = not kpi.is_active
    return kpi


def delete_kpi(kpi_id):
    kpi = KPI.query.get(kpi_id)
    if not kpi:
        raise ValueError("المؤشر غير موجود.")
    if kpi.is_default:
        raise ValueError("لا يمكن حذف مؤشر النظام الافتراضي — عطّله بدلاً من ذلك.")
    if StudentKPI.query.filter_by(kpi_id=kpi.id).first():
        kpi.is_active = False
        return kpi, "deactivated"
    db.session.delete(kpi)
    return kpi, "deleted"


def update_kpi_weights(form, school_id):
    query = kpi_query_for_school(school_id, active_only=False)
    updated = 0
    for kpi in query.all():
        val = form.get(f"weight_{kpi.id}")
        if val is not None and val != "":
            kpi.weight = float(val)
            updated += 1
    return updated


def save_kpi_period_settings(school_id, form):
    """Persist KPI period labels and day windows from admin form."""
    from app.services.config_service import set_setting

    pairs = [
        ("kpi_period_term_label", form.get("kpi_period_term_label")),
        ("kpi_period_monthly_label", form.get("kpi_period_monthly_label")),
        ("kpi_period_weekly_label", form.get("kpi_period_weekly_label")),
        ("kpi_period_daily_label", form.get("kpi_period_daily_label")),
        ("kpi_period_days_term", form.get("kpi_period_days_term")),
        ("kpi_period_days_monthly", form.get("kpi_period_days_monthly")),
        ("kpi_period_days_weekly", form.get("kpi_period_days_weekly")),
        ("kpi_period_days_daily", form.get("kpi_period_days_daily")),
    ]
    for key, val in pairs:
        if val is not None and str(val).strip() != "":
            set_setting(key, str(val).strip(), school_id, "kpi", key)
    return len([p for p in pairs if p[1]])
