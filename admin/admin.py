from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from models.models import db, Item

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/panel')
@login_required
def admin_panel():
    if not current_user.is_admin:
        flash('Admin access only.')
        return redirect(url_for('index'))
    items = Item.query.all()
    return render_template('admin_panel.html', items=items)

@admin_bp.route('/approve/<int:item_id>')
@login_required
def approve_item(item_id):
    if not current_user.is_admin:
        flash('Admin access only.')
        return redirect(url_for('index'))
    item = Item.query.get_or_404(item_id)
    item.status = 'available'
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))

@admin_bp.route('/reject/<int:item_id>')
@login_required
def reject_item(item_id):
    if not current_user.is_admin:
        flash('Admin access only.')
        return redirect(url_for('index'))
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('admin.admin_panel'))
