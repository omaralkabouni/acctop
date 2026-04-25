import os
from flask import render_template, redirect, url_for, flash, send_from_directory, current_app
from flask_login import login_required
from . import backups_bp
from ...utils.backup import create_backup, list_backups, get_backup_dir
from ...utils.decorators import role_required, log_action

@backups_bp.route('/')
@login_required
@role_required('admin')
def index():
    backups = list_backups()
    return render_template('backups/index.html', title='النسخ الاحتياطي', backups=backups)

@backups_bp.route('/create')
@login_required
@role_required('admin')
def run_backup():
    try:
        filename = create_backup()
        flash(f'تم إنشاء النسخة الاحتياطية {filename} بنجاح', 'success')
        log_action(None, 'create', 'Backup', None, new_values={'filename': filename})
    except Exception as e:
        flash(f'خطأ أثناء إنشاء النسخة الاحتياطية: {e}', 'error')
    return redirect(url_for('backups.index'))

@backups_bp.route('/download/<filename>')
@login_required
@role_required('admin')
def download(filename):
    directory = get_backup_dir()
    return send_from_directory(directory, filename, as_attachment=True)

@backups_bp.route('/delete/<filename>', methods=['POST'])
@login_required
@role_required('admin')
def delete(filename):
    directory = get_backup_dir()
    file_path = os.path.join(directory, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        flash('تم حذف النسخة الاحتياطية بنجاح', 'success')
    return redirect(url_for('backups.index'))

@backups_bp.route('/api/daily')
def daily_backup():
    # This can be called by an external cron/task scheduler
    try:
        filename = create_backup(send_to_n8n=True)
        return f"Daily backup created and sent to n8n: {filename}", 200
    except Exception as e:
        return f"Backup failed: {e}", 500

@backups_bp.route('/restore/<filename>', methods=['POST'])
@login_required
@role_required('admin')
def restore(filename):
    try:
        from ...utils.backup import restore_backup
        restore_backup(filename)
        flash('تم استعادة النسخة الاحتياطية بنجاح. قد تحتاج لإعادة تسجيل الدخول.', 'success')
    except Exception as e:
        flash(f'فشل استعادة النسخة: {e}', 'error')
    return redirect(url_for('backups.index'))

@backups_bp.route('/upload', methods=['POST'])
@login_required
@role_required('admin')
def upload():
    if 'backup_file' not in request.files:
        flash('لم يتم اختيار ملف', 'error')
        return redirect(url_for('backups.index'))
    
    file = request.files['backup_file']
    if file.filename == '':
        flash('لم يتم اختيار ملف', 'error')
        return redirect(url_for('backups.index'))

    if file and file.filename.endswith('.db'):
        directory = get_backup_dir()
        filename = f"uploaded_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
        file.save(os.path.join(directory, filename))
        flash('تم رفع الملف بنجاح. يمكنك الآن الضغط على "استعادة" بجانبه.', 'success')
    else:
        flash('يرجى اختيار ملف قاعدة بيانات صحيح بصيغة .db', 'error')
        
    return redirect(url_for('backups.index'))
