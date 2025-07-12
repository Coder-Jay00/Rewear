import os
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models.models import db, User, Item, SwapRequest
from admin.admin import admin_bp
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

app.register_blueprint(admin_bp)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    items = Item.query.filter_by(status='available').all()
    featured_items = Item.query.filter_by(status='approved').order_by(Item.id.desc()).limit(8).all()
    if not featured_items:
        featured_items = Item.query.order_by(Item.id.desc()).limit(8).all()
    return render_template('index.html', featured_items=featured_items, items=items)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']  # Get the name from the form
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        user = User(name=name, email=email, password=password)  # Store the name
        db.session.add(user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    my_items = Item.query.filter_by(uploader_id=current_user.id).all()
    my_requests = SwapRequest.query.filter_by(requester_id=current_user.id).all()

    # Attach item title to each request (without changing the model)
    for req in my_requests:
        item = Item.query.get(req.item_id)
        req.item_title = item.title if item else "Unknown Item"


    return render_template(
        "dashboard.html",
        my_items=my_items,
        my_requests=my_requests
    )


@app.route('/add_item', methods=['GET', 'POST'])
@login_required
def add_item():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        type_ = request.form['type']
        size = request.form['size']
        condition = request.form['condition']
        tags = request.form['tags']
        file = request.files['image']
        filename = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        item = Item(
            title=title,
            description=description,
            category=category,
            type=type_,
            size=size,
            condition=condition,
            tags=tags,
            image_filename=filename,
            uploader_id=current_user.id,
            status='pending'
        )
        db.session.add(item)
        current_user.points += 5  # Reward points for listing an item
        db.session.commit()
        flash('Item submitted for approval.')
        return redirect(url_for('dashboard'))
    return render_template('add_item.html')

@app.route('/item/<int:item_id>', methods=['GET', 'POST'])
def item_detail(item_id):
    item = Item.query.get_or_404(item_id)
    uploader = User.query.get(item.uploader_id)
    my_items = []
    if current_user.is_authenticated:
        my_items = Item.query.filter_by(uploader_id=current_user.id, status='available').all()
    return render_template('item_detail.html', item=item, uploader=uploader, my_items=my_items)


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/marketplace')
@login_required
def marketplace():
    # Show items not uploaded by the current user and that are available
    items = Item.query.filter(Item.uploader_id != current_user.id, Item.status == 'available').all()
    return render_template('marketplace.html', items=items)

@app.route('/swap_request/<int:item_id>', methods=['POST'])
@login_required
def swap_request(item_id):
    item = Item.query.get_or_404(item_id)
    swap_type = request.form['swap_type']

    offered_item_id = None
    if swap_type == 'swap':
        offered_item_id = int(request.form.get('offered_item_id'))
        # Check for duplicate swap request
        duplicate = SwapRequest.query.filter_by(
            item_id=item.id,
            requester_id=current_user.id,
            offered_item_id=offered_item_id,
            type='swap',
            status='pending'
        ).first()
        if duplicate:
            flash('You have already sent a swap request for this item with this offer.')
            return redirect(url_for('item_detail', item_id=item_id))
        offered_item = Item.query.filter_by(id=offered_item_id, uploader_id=current_user.id, status='available').first()
        if not offered_item:
            flash('Invalid swap: You must select one of your available items.')
            return redirect(url_for('item_detail', item_id=item_id))
    else:
        # Check for duplicate buy request
        if current_user.points < 100:
            flash('Not enough points to redeem this item.')
            return redirect(url_for('item_detail', item_id=item_id))
        current_user.points -= 100
        db.session.commit()
        duplicate = SwapRequest.query.filter_by(
            item_id=item.id,
            requester_id=current_user.id,
            type='buy',
            status='pending'
        ).first()
        if duplicate:
            flash('You have already sent a buy request for this item.')
            return redirect(url_for('item_detail', item_id=item_id))
        offered_item = None

    if item.uploader_id == current_user.id or item.status != 'available':
        flash('Invalid request.')
        return redirect(url_for('item_detail', item_id=item_id))

    swap = SwapRequest(
        item_id=item.id,
        requester_id=current_user.id,
        offered_item_id=offered_item.id if offered_item else None,
        type=swap_type
    )
    db.session.add(swap)
    db.session.commit()
    flash('Swap request sent to the item owner.')
    return redirect(url_for('item_detail', item_id=item_id))





from flask_login import login_required, current_user
from models.models import SwapRequest, Item

@app.route('/my_swap_requests')
@login_required
def my_swap_requests():
    # Get all swap requests made by the current user
    swap_requests = SwapRequest.query.filter_by(requester_id=current_user.id).all()
    # Optionally, get related item info for display
    items = {req.item_id: Item.query.get(req.item_id) for req in swap_requests}
    return render_template('my_swap_requests.html', swap_requests=swap_requests, items=items)


from flask_login import login_required, current_user
from models.models import SwapRequest, Item, User

@app.route('/incoming_swap_requests')
@login_required
def incoming_swap_requests():
    # Get all items owned by current user
    user_items = Item.query.filter_by(uploader_id=current_user.id).all()
    user_item_ids = [item.id for item in user_items]

    # Get all swap requests for these items
    swap_requests = SwapRequest.query.filter(SwapRequest.item_id.in_(user_item_ids)).all()

    # Collect all relevant item IDs (requested and offered)
    all_item_ids = set(user_item_ids)
    for req in swap_requests:
        if req.offered_item_id:
            all_item_ids.add(req.offered_item_id)

    # Fetch all relevant items
    all_items = Item.query.filter(Item.id.in_(all_item_ids)).all()
    items = {item.id: item for item in all_items}

    # Get requester info as before
    requesters = {req.requester_id: User.query.get(req.requester_id) for req in swap_requests}

    return render_template(
        'incoming_swap_requests.html',
        swap_requests=swap_requests,
        items=items,
        requesters=requesters
    )

from flask import abort
from flask_login import current_user

@app.route('/admin/delete_swap_request/<int:swap_id>', methods=['POST'])
@login_required
def delete_swap_request(swap_id):
    if not current_user.is_admin:
        abort(403)
    swap = SwapRequest.query.get_or_404(swap_id)
    db.session.delete(swap)
    db.session.commit()
    flash('Swap request deleted.')
    return redirect(url_for('admin_swap_requests'))  # Adjust this to your admin page


@app.route('/admin/swap_requests')
@login_required
def admin_swap_requests():
    if not current_user.is_admin:
        abort(403)
    swap_requests = SwapRequest.query.order_by(SwapRequest.id.desc()).all()
    # Gather all item and user IDs involved
    item_ids = set()
    user_ids = set()
    for req in swap_requests:
        item_ids.add(req.item_id)
        if req.offered_item_id:
            item_ids.add(req.offered_item_id)
        user_ids.add(req.requester_id)
    items = {item.id: item for item in Item.query.filter(Item.id.in_(item_ids)).all()}
    users = {user.id: user for user in User.query.filter(User.id.in_(user_ids)).all()}
    return render_template(
        'admin_swap_requests.html',
        swap_requests=swap_requests,
        items=items,
        users=users
    )

from flask import request, redirect, url_for, flash
from flask_login import login_required, current_user

@app.route('/swap_request_action/<int:swap_id>', methods=['POST'])
@login_required
def handle_swap_request_action(swap_id):
    swap = SwapRequest.query.get_or_404(swap_id)
    item = Item.query.get(swap.item_id)
    if item.uploader_id != current_user.id:
        flash("You are not authorized to perform this action.")
        return redirect(url_for('incoming_swap_requests'))

    action = request.form.get('action')
    if action == 'approve':
        swap.status = 'approved'
        item.status = 'swapped'
        # Award points to item owner
        owner = User.query.get(item.uploader_id)
        if owner:
            owner.points += 10
        # If swap, mark offered item as swapped and award points to offerer
        if swap.offered_item_id:
            offered_item = Item.query.get(swap.offered_item_id)
            if offered_item:
                offered_item.status = 'swapped'
                offerer = User.query.get(swap.requester_id)
                if offerer:
                    offerer.points += 10
        db.session.commit()
        flash("Swap request approved. Points awarded!")
    elif action == 'reject':
        swap.status = 'rejected'
        db.session.commit()
        flash("Swap request rejected.")
    else:
        flash("Invalid action.")

    return redirect(url_for('incoming_swap_requests'))

from flask import redirect, url_for, flash
from flask_login import login_required, current_user

@app.route('/admin/delete_item/<int:item_id>', methods=['POST'])
@login_required
def admin_delete_item(item_id):
    if not current_user.is_admin:
        flash("Unauthorized", "danger")
        return redirect(url_for('dashboard'))
    item = Item.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Item deleted.", "success")
    return redirect(url_for('dashboard'))  # or admin panel

@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    if item.uploader_id != current_user.id and not current_user.is_admin:
        abort(403)
    if request.method == 'POST':
        item.title = request.form['title']
        item.category = request.form['category']
        item.size = request.form['size']
        item.condition = request.form['condition']
        item.description = request.form['description']
        # Handle image upload if needed
        db.session.commit()
        flash('Item updated successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_item.html', item=item)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
