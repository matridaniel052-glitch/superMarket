from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db
from app.models import Supplier, PurchaseOrder, POItem, Product
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os

suppliers = Blueprint('suppliers', __name__)


@suppliers.route('/suppliers')
@login_required
def index():
    all_suppliers = Supplier.query.order_by(Supplier.name).all()
    return render_template('suppliers/index.html', suppliers=all_suppliers)


@suppliers.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        name          = request.form.get('name', '').strip()
        contact       = request.form.get('contact', '').strip()
        email         = request.form.get('email', '').strip()
        phone         = request.form.get('phone', '').strip()
        address       = request.form.get('address', '').strip()
        payment_terms = request.form.get('payment_terms', '').strip()
        if not name:
            flash('Supplier name is required.', 'error')
            return redirect(url_for('suppliers.add'))
        s = Supplier(name=name, contact=contact, email=email,
                     phone=phone, address=address, payment_terms=payment_terms)
        db.session.add(s)
        db.session.commit()
        flash(f'Supplier "{name}" added successfully!', 'success')
        return redirect(url_for('suppliers.index'))
    return render_template('suppliers/add.html')


@suppliers.route('/suppliers/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    s = Supplier.query.get_or_404(id)
    if request.method == 'POST':
        s.name          = request.form.get('name', '').strip()
        s.contact       = request.form.get('contact', '').strip()
        s.email         = request.form.get('email', '').strip()
        s.phone         = request.form.get('phone', '').strip()
        s.address       = request.form.get('address', '').strip()
        s.payment_terms = request.form.get('payment_terms', '').strip()
        db.session.commit()
        flash(f'Supplier "{s.name}" updated!', 'success')
        return redirect(url_for('suppliers.index'))
    return render_template('suppliers/edit.html', supplier=s)


@suppliers.route('/suppliers/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    s = Supplier.query.get_or_404(id)
    name = s.name
    db.session.delete(s)
    db.session.commit()
    flash(f'Supplier "{name}" deleted.', 'info')
    return redirect(url_for('suppliers.index'))


@suppliers.route('/suppliers/<int:supplier_id>/orders')
@login_required
def orders(supplier_id):
    s        = Supplier.query.get_or_404(supplier_id)
    products = Product.query.order_by(Product.name).all()
    return render_template('suppliers/orders.html', supplier=s, products=products)


@suppliers.route('/suppliers/<int:supplier_id>/orders/create', methods=['POST'])
@login_required
def create_order(supplier_id):
    s           = Supplier.query.get_or_404(supplier_id)
    product_ids = request.form.getlist('product_id')
    quantities  = request.form.getlist('quantity')
    cost_prices = request.form.getlist('cost_price')
    notes       = request.form.get('notes', '').strip()

    if not product_ids:
        flash('Add at least one product to the order.', 'error')
        return redirect(url_for('suppliers.orders', supplier_id=supplier_id))

    po = PurchaseOrder(supplier_id=supplier_id, notes=notes)
    db.session.add(po)
    db.session.flush()

    for pid, qty, cp in zip(product_ids, quantities, cost_prices):
        qty = int(qty)  if qty else 0
        cp  = float(cp) if cp  else 0.0
        if qty <= 0:
            continue
        item = POItem(order_id=po.id, product_id=int(pid), quantity=qty, cost_price=cp)
        db.session.add(item)

    po.total_cost = po.computed_total
    db.session.commit()
    flash(f'Purchase order #{po.id} created successfully!', 'success')
    return redirect(url_for('suppliers.orders', supplier_id=supplier_id))


@suppliers.route('/orders/update-status/<int:order_id>', methods=['POST'])
@login_required
def update_status(order_id):
    po     = PurchaseOrder.query.get_or_404(order_id)
    status = request.form.get('status')
    po.status = status

    if status == 'delivered':
        for item in po.items:
            item.product.quantity  += item.quantity
            item.product.cost_price = item.cost_price
        flash(f'Order #{po.id} marked as delivered — stock updated!', 'success')
    else:
        flash(f'Order #{po.id} status updated to {status}.', 'success')

    db.session.commit()
    return redirect(url_for('suppliers.orders', supplier_id=po.supplier_id))


@suppliers.route('/orders/delete/<int:order_id>', methods=['POST'])
@login_required
def delete_order(order_id):
    po  = PurchaseOrder.query.get_or_404(order_id)
    sid = po.supplier_id
    db.session.delete(po)
    db.session.commit()
    flash('Purchase order deleted.', 'info')
    return redirect(url_for('suppliers.orders', supplier_id=sid))


@suppliers.route('/orders/send-email', methods=['POST'])
@login_required
def send_order_email():
    order_id = request.form.get('order_id', type=int)
    to_email = request.form.get('to_email', '').strip()
    subject  = request.form.get('subject', '').strip()
    message  = request.form.get('message', '').strip()

    po = PurchaseOrder.query.get_or_404(order_id)

    smtp_host = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.getenv('MAIL_PORT', '587'))
    smtp_user = os.getenv('EMAIL_USER', '')
    smtp_pass = os.getenv('EMAIL_PASS', '')
    from_addr = smtp_user

    if not smtp_user or not smtp_pass:
        flash('Email not configured. Add EMAIL_USER and EMAIL_PASS to Railway variables.', 'error')
        return redirect(url_for('suppliers.orders', supplier_id=po.supplier_id))

    items_rows = ''.join(
        f'<tr><td style="padding:8px 12px;border-bottom:1px solid #e5e7ef;">{item.product.name}</td>'
        f'<td style="padding:8px 12px;text-align:center;border-bottom:1px solid #e5e7ef;">{item.quantity}</td>'
        f'<td style="padding:8px 12px;text-align:right;border-bottom:1px solid #e5e7ef;">GHS {item.cost_price:.2f}</td>'
        f'<td style="padding:8px 12px;text-align:right;font-weight:600;border-bottom:1px solid #e5e7ef;">GHS {item.subtotal:.2f}</td></tr>'
        for item in po.items
    )

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:#2563eb;padding:24px;border-radius:10px 10px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:20px;">SuperMart IMS</h1>
        <p style="color:#bfdbfe;margin:4px 0 0;font-size:13px;">Purchase Order Notification</p>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #e5e7ef;">
        <p style="white-space:pre-line;font-size:14px;line-height:1.6;">{message}</p>
        <h3 style="font-size:14px;color:#374151;">PO-{po.id:05d} &middot; {po.order_date.strftime('%d %B %Y')}</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
          <thead><tr style="background:#f8f9fc;">
            <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #e5e7ef;">Product</th>
            <th style="padding:10px 12px;text-align:center;border-bottom:2px solid #e5e7ef;">Qty</th>
            <th style="padding:10px 12px;text-align:right;border-bottom:2px solid #e5e7ef;">Unit Cost</th>
            <th style="padding:10px 12px;text-align:right;border-bottom:2px solid #e5e7ef;">Subtotal</th>
          </tr></thead>
          <tbody>{items_rows}</tbody>
          <tfoot><tr style="background:#eff6ff;">
            <td colspan="3" style="padding:12px;font-weight:700;text-align:right;">Total</td>
            <td style="padding:12px;font-weight:700;text-align:right;color:#2563eb;">GHS {po.computed_total:.2f}</td>
          </tr></tfoot>
        </table>
      </div>
      <div style="background:#f8f9fc;padding:14px 24px;border:1px solid #e5e7ef;border-radius:0 0 10px 10px;">
        <p style="font-size:11px;color:#9ca3af;margin:0;">Sent by SuperMart IMS &middot; {current_user.full_name}</p>
      </div>
    </div>"""

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'SuperMart IMS <{from_addr}>'
        msg['To']      = to_email
        msg.attach(MIMEText(message,   'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, to_email, msg.as_string())

        flash(f'Purchase order emailed to {to_email} successfully!', 'success')

    except smtplib.SMTPAuthenticationError:
        flash('Email failed: check EMAIL_USER and EMAIL_PASS in Railway variables.', 'error')
    except Exception as e:
        flash(f'Email error: {str(e)}', 'error')

    return redirect(url_for('suppliers.orders', supplier_id=po.supplier_id))