"""Inventory routes — product and stock management."""
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user

from . import inventory_bp
from ...extensions import db
from ...models.product import Product, InventoryMovement
from ...models.account import Account
from ...utils.decorators import permission_required, log_action


@inventory_bp.route('/')
@inventory_bp.route('/products')
@login_required
def index():
    search = request.args.get('q', '')
    category = request.args.get('category', '')
    page = request.args.get('page', 1, type=int)

    q = Product.query.filter_by(is_active=True)
    if search:
        q = q.filter(Product.name.ilike(f'%{search}%') | Product.sku.ilike(f'%{search}%'))
    if category:
        q = q.filter_by(category=category)

    products = q.order_by(Product.name).paginate(page=page, per_page=25)
    categories = db.session.query(Product.category).distinct().all()
    total_value = sum(p.stock_value for p in Product.query.filter_by(is_active=True))

    return render_template('inventory/index.html', title='المخزون',
                           products=products, categories=categories,
                           total_value=total_value, search=search, category=category)


from werkzeug.utils import secure_filename
import os

@inventory_bp.route('/products/create', methods=['GET', 'POST'])
@login_required
@permission_required('inventory')
def create_product():
    accounts = Account.query.filter_by(type='asset', is_active=True).all()
    if request.method == 'POST':
        # Handle Multiple Image Uploads
        image_files = request.files.getlist('images')
        primary_image = None
        
        product = Product(
            sku=request.form.get('sku', '').strip() or None,
            name=request.form.get('name', '').strip(),
            name_ar=request.form.get('name_ar', '').strip() or None,
            category=request.form.get('category', '').strip(),
            description=request.form.get('description', '').strip(),
            unit_price=float(request.form.get('unit_price', 0)),
            cost_price=float(request.form.get('cost_price', 0)),
            stock_qty=float(request.form.get('stock_qty', 0)),
            min_stock=float(request.form.get('min_stock', 0)),
            unit=request.form.get('unit', 'قطعة'),
            account_id=request.form.get('account_id', type=int) if request.form.get('account_id') else None,
        )
        db.session.add(product)
        db.session.flush()

        from werkzeug.utils import secure_filename
        import os
        from datetime import datetime

        for i, img in enumerate(image_files):
            if img and img.filename:
                filename = secure_filename(img.filename)
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}_{filename}"
                upload_dir = os.path.join(current_app.static_folder, 'uploads', 'products')
                if not os.path.exists(upload_dir): os.makedirs(upload_dir, exist_ok=True)
                img.save(os.path.join(upload_dir, filename))
                
                # First image is primary
                if i == 0:
                    product.image = filename
                
                new_img = ProductImage(product_id=product.id, image=filename, is_primary=(i==0))
                db.session.add(new_img)


        if float(product.stock_qty) > 0:
            mov = InventoryMovement(
                product_id=product.id, type='in',
                qty=product.stock_qty, unit_cost=product.cost_price,
                reference='رصيد ابتدائي', created_by=current_user.id,
            )
            db.session.add(mov)

        db.session.commit()
        log_action(current_user.id, 'create', 'Product', product.id,
                   new_values={'name': product.name, 'sku': product.sku})
        flash(f'تم إضافة المنتج {product.name} بنجاح', 'success')
        return redirect(url_for('inventory.index'))

    return render_template('inventory/product_form.html', title='إضافة منتج',
                           product=None, accounts=accounts)


@inventory_bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required('inventory')
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    accounts = Account.query.filter_by(type='asset', is_active=True).all()
    if request.method == 'POST':
        # Handle Image Deletion
        deleted_image_ids = request.form.getlist('delete_images[]')
        for img_id in deleted_image_ids:
            img_obj = ProductImage.query.get(int(img_id))
            if img_obj:
                # If it was the primary image of the product model, clear it
                if product.image == img_obj.image:
                    product.image = None
                db.session.delete(img_obj)

        # Handle New Image Uploads
        image_files = request.files.getlist('images')
        from werkzeug.utils import secure_filename
        import os
        from datetime import datetime

        for i, img in enumerate(image_files):
            if img and img.filename:
                filename = secure_filename(img.filename)
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}_{filename}"
                upload_dir = os.path.join(current_app.static_folder, 'uploads', 'products')
                if not os.path.exists(upload_dir): os.makedirs(upload_dir, exist_ok=True)
                img.save(os.path.join(upload_dir, filename))
                
                # Set as primary if product has no primary image
                if not product.image:
                    product.image = filename
                
                new_img = ProductImage(product_id=product.id, image=filename, is_primary=False)
                db.session.add(new_img)


        old_vals = {'name': product.name, 'stock_qty': float(product.stock_qty)}
        product.name = request.form.get('name', product.name).strip()
        product.name_ar = request.form.get('name_ar', '').strip() or None
        product.sku = request.form.get('sku', product.sku).strip() or None
        product.category = request.form.get('category', product.category).strip()
        product.description = request.form.get('description', '').strip()
        product.unit_price = float(request.form.get('unit_price', product.unit_price))
        product.cost_price = float(request.form.get('cost_price', product.cost_price))
        product.min_stock = float(request.form.get('min_stock', product.min_stock))
        product.unit = request.form.get('unit', product.unit)
        product.is_active = bool(request.form.get('is_active'))
        product.account_id = request.form.get('account_id', type=int) if request.form.get('account_id') else product.account_id
        db.session.commit()
        log_action(current_user.id, 'update', 'Product', product.id, old_values=old_vals,
                   new_values={'name': product.name, 'unit_price': float(product.unit_price)})
        flash('تم تحديث المنتج بنجاح', 'success')
        return redirect(url_for('inventory.index'))
    return render_template('inventory/product_form.html', title='تعديل منتج',
                           product=product, accounts=accounts)


@inventory_bp.route('/products/<int:product_id>/adjust', methods=['GET', 'POST'])
@login_required
@permission_required('inventory')
def adjust_stock(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        mov_type = request.form.get('type', 'in')
        qty = float(request.form.get('qty', 0))
        unit_cost = float(request.form.get('unit_cost', product.cost_price))
        notes = request.form.get('notes', '')

        if mov_type == 'out' and float(product.stock_qty) < qty:
            flash('الكمية المطلوبة أكبر من المخزون المتاح', 'error')
            return redirect(url_for('inventory.adjust_stock', product_id=product_id))

        mov = InventoryMovement(
            product_id=product.id, type=mov_type,
            qty=qty, unit_cost=unit_cost,
            reference=notes or f'تسوية يدوية',
            notes=notes, created_by=current_user.id,
        )
        db.session.add(mov)

        if mov_type == 'in':
            product.stock_qty = float(product.stock_qty) + qty
        elif mov_type == 'out':
            product.stock_qty = float(product.stock_qty) - qty
        else:  # adjustment
            product.stock_qty = qty

        db.session.commit()
        flash(f'تم تحديث المخزون بنجاح', 'success')
        return redirect(url_for('inventory.product_movements', product_id=product_id))

    return render_template('inventory/adjust_stock.html', title='تسوية المخزون', product=product)


@inventory_bp.route('/products/<int:product_id>')
@login_required
def view_product(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('inventory/view.html', title=product.name, product=product)


@inventory_bp.route('/p/<int:product_id>')
def public_product(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.is_active:
        return "المنتج غير متوفر حالياً", 404
    return render_template('inventory/public_view.html', title=product.name, product=product)


@inventory_bp.route('/products/<int:product_id>/movements')
@login_required
def product_movements(product_id):
    product = Product.query.get_or_404(product_id)
    movements = InventoryMovement.query.filter_by(product_id=product_id).order_by(
        InventoryMovement.created_at.desc()).all()
    return render_template('inventory/movements.html', title=f'حركة {product.name}',
                           product=product, movements=movements)
