from datetime import datetime, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from flask_jwt_extended import create_access_token

from app.auth import bp
from app.extensions import db
from app.models import User, AuditLog


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboards.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username, is_active=True).first()

        if user and user.check_password(password):
            login_user(user, remember=bool(request.form.get("remember")))
            user.last_login = datetime.now(timezone.utc)
            db.session.add(AuditLog(
                user_id=user.id,
                action="login",
                module="auth",
                ip_address=request.remote_addr,
            ))
            db.session.commit()
            flash(f"مرحباً {user.full_name_ar or user.full_name}", "success")
            next_page = request.args.get("next")
            return redirect(next_page or url_for("dashboards.index"))

        flash("اسم المستخدم أو كلمة المرور غير صحيحة.", "danger")

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    db.session.add(AuditLog(
        user_id=current_user.id,
        action="logout",
        module="auth",
        ip_address=request.remote_addr,
    ))
    db.session.commit()
    logout_user()
    flash("تم تسجيل الخروج بنجاح.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/api/token", methods=["POST"])
def api_token():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    user = User.query.filter_by(username=username, is_active=True).first()

    if not user or not user.check_password(password):
        return {"error": "بيانات الدخول غير صحيحة"}, 401

    token = create_access_token(identity=str(user.id), additional_claims={
        "role": user.role.name,
        "school_id": user.school_id,
    })
    return {"access_token": token, "role": user.role.name}
