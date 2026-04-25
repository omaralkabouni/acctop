"""Settings routes."""
import os
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from . import settings_bp
from ...extensions import db
from ...models.settings import SystemSettings
from ...utils.decorators import role_required, log_action

@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def index():
    settings = SystemSettings.get_settings()
    
    if request.method == 'POST':
        # Update text fields
        settings.company_name = request.form.get('company_name', settings.company_name).strip()
        settings.tax_rate = float(request.form.get('tax_rate', settings.tax_rate))
        settings.show_tax = 'show_tax' in request.form
        settings.currency_symbol = request.form.get('currency_symbol', settings.currency_symbol).strip()
        settings.exchange_rate = float(request.form.get('exchange_rate', settings.exchange_rate))
        settings.n8n_webhook_url = request.form.get('n8n_webhook_url', settings.n8n_webhook_url).strip()
        
        # Handle Logo Upload
        if 'company_logo' in request.files:
            file = request.files['company_logo']
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Create uploads directory if not exists
                upload_path = os.path.join(current_app.static_folder, 'uploads')
                if not os.path.exists(upload_path):
                    os.makedirs(upload_path)
                
                file.save(os.path.join(upload_path, filename))
                settings.company_logo = f'uploads/{filename}'
        
        db.session.commit()
        log_action(current_user.id, 'update', 'Settings', settings.id)
        flash('تم تحديث الإعدادات بنجاح', 'success')
        return redirect(url_for('settings.index'))
        
    return render_template('settings/index.html', title='الإعدادات العامة', settings=settings)
