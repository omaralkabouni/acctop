"""Auth routes — login, logout, user management."""
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from . import auth_bp
from ...extensions import db
from ...models.user import User, Role
from ...utils.decorators import role_required, log_action


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            log_action(user.id, 'login', 'User', user.id)
            next_page = request.args.get('next')
            flash(f'مرحباً {user.full_name}!', 'success')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')

    return render_template('auth/login.html', title='تسجيل الدخول')


@auth_bp.route('/logout')
@login_required
def logout():
    log_action(current_user.id, 'logout', 'User', current_user.id)
    logout_user()
    flash('تم تسجيل الخروج بنجاح', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/users')
@login_required
@role_required('admin')
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    roles = Role.query.all()
    return render_template('auth/users.html', title='إدارة المستخدمين',
                           users=all_users, roles=roles)


@auth_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_user():
    roles = Role.query.all()
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        role_id = request.form.get('role_id', type=int)

        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم موجود بالفعل', 'error')
        elif User.query.filter_by(email=email).first():
            flash('البريد الإلكتروني موجود بالفعل', 'error')
        else:
            user = User(username=username, email=email, full_name=full_name, role_id=role_id)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            log_action(current_user.id, 'create', 'User', user.id, new_values={'username': username})
            flash(f'تم إنشاء المستخدم {full_name} بنجاح', 'success')
            return redirect(url_for('auth.users'))

    return render_template('auth/user_form.html', title='إضافة مستخدم', roles=roles, user=None)


@auth_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    roles = Role.query.all()

    if request.method == 'POST':
        old_vals = {'full_name': user.full_name, 'role_id': user.role_id}
        user.full_name = request.form.get('full_name', user.full_name).strip()
        user.email = request.form.get('email', user.email).strip()
        user.role_id = request.form.get('role_id', user.role_id, type=int)
        user.is_active = bool(request.form.get('is_active'))
        new_pwd = request.form.get('password', '')
        if new_pwd:
            user.set_password(new_pwd)
        db.session.commit()
        log_action(current_user.id, 'update', 'User', user.id, old_values=old_vals,
                   new_values={'full_name': user.full_name, 'role_id': user.role_id})
        flash('تم تحديث المستخدم بنجاح', 'success')
        return redirect(url_for('auth.users'))

    return render_template('auth/user_form.html', title='تعديل مستخدم', roles=roles, user=user)


@auth_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@role_required('admin')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('لا يمكنك حذف حسابك الخاص', 'error')
        return redirect(url_for('auth.users'))
    log_action(current_user.id, 'delete', 'User', user.id, old_values={'username': user.username})
    db.session.delete(user)
    db.session.commit()
    flash('تم حذف المستخدم بنجاح', 'success')
    return redirect(url_for('auth.users'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.full_name = request.form.get('full_name', current_user.full_name).strip()
        current_user.email = request.form.get('email', current_user.email).strip()
        new_pwd = request.form.get('new_password', '')
        if new_pwd:
            old_pwd = request.form.get('current_password', '')
            if not current_user.check_password(old_pwd):
                flash('كلمة المرور الحالية غير صحيحة', 'error')
                return redirect(url_for('auth.profile'))
            current_user.set_password(new_pwd)
        db.session.commit()
        flash('تم تحديث الملف الشخصي بنجاح', 'success')
        return redirect(url_for('auth.profile'))
    return render_template('auth/profile.html', title='الملف الشخصي')
