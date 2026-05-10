from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_required, current_user
from functools import wraps

settings = Blueprint('settings', __name__)

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role not in ['admin', 'stock_manager']:
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated

@settings.route('/settings')
@login_required
@admin_required
def index():
    config = session.get('sys_config', {})
    return render_template('settings/index.html', config=config)

@settings.route('/settings/save', methods=['POST'])
@login_required
@admin_required
def save():
    config = session.get('sys_config', {})
    section = request.form.get('section')

    if section == 'store':
        config['store_name']    = request.form.get('store_name', 'matri-link')
        config['store_phone']   = request.form.get('store_phone', '')
        config['store_email']   = request.form.get('store_email', '')
        config['store_address'] = request.form.get('store_address', '')
        flash('Store information saved!', 'success')

    elif section == 'finance':
        config['currency'] = request.form.get('currency', 'GHS')
        config['vat_rate'] = request.form.get('vat_rate', '0')
        flash('Finance settings saved!', 'success')

    session['sys_config'] = config
    return redirect(url_for('settings.index'))