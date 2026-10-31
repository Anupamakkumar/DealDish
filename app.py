import os, math, re, uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dealdish-local-demo-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'dealdish.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB per image
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    phone = db.Column(db.String(20), default='')
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='customer')
    coins = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Hotel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    fssai = db.Column(db.String(12), nullable=False)
    description = db.Column(db.String(500), default='')
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    closing_time = db.Column(db.String(10), default='22:00')
    status = db.Column(db.String(20), default='pending')
    admin_note = db.Column(db.String(300), default='')
    user = db.relationship('User', backref=db.backref('hotel_profile', uselist=False))

class Deal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotel.id'), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(500), default='')
    original_price = db.Column(db.Float, nullable=False)
    deal_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    image_url = db.Column(db.String(500), default='')
    available_from = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    active = db.Column(db.Boolean, default=True)
    hotel = db.relationship('Hotel', backref='deals')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    deal_id = db.Column(db.Integer, db.ForeignKey('deal.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Float, nullable=False)
    fulfilment = db.Column(db.String(20), nullable=False)
    payment = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(30), default='Placed')
    reservation_expires = db.Column(db.DateTime)
    cancellation_reason = db.Column(db.String(300), default='')
    cancelled_at = db.Column(db.DateTime)
    refund_status = db.Column(db.String(30), default='Not applicable')
    refund_amount = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='orders')
    deal = db.relationship('Deal', backref='orders')

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    deal_id = db.Column(db.Integer, db.ForeignKey('deal.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # food rating (backward compatible)
    hotel_rating = db.Column(db.Integer, nullable=False, default=5)
    comment = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User')
    deal = db.relationship('Deal', backref=db.backref('reviews', lazy=True))

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(300), nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='notices')

def current_user():
    return db.session.get(User, session.get('user_id')) if session.get('user_id') else None

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash('Please sign in to continue.', 'info')
            return redirect(url_for('login', next=request.path))
        return fn(*args, **kwargs)
    return wrapped

def roles_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = current_user()
            if not user:
                flash('Please sign in first.', 'info'); return redirect(url_for('login'))
            if user.role not in roles:
                flash('You do not have permission to access that page.', 'danger'); return redirect(url_for('index'))
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def is_live(deal):
    return deal.active and deal.quantity > 0 and deal.expires_at > datetime.utcnow()

def notify(user_id, message):
    db.session.add(Notice(user_id=user_id, message=message))

def seed_data():
    if not User.query.filter_by(email='admin@dealdish.local').first():
        db.session.add(User(name='DealDish Admin', email='admin@dealdish.local', password_hash=generate_password_hash('Admin@123'), role='admin'))
    db.session.commit()
    if Deal.query.count() == 0:
        demo = [
            ('Green Leaf Kitchen','Ottapalam Main Road','987654321001','Kerala meals box','Meals',120,69,8,'https://images.unsplash.com/photo-1546833999-b9f581a1996d?auto=format&fit=crop&w=900&q=85'),
            ('Malabar Bites','Palakkad Town','987654321002','Chicken biryani','Rice & Biryani',180,109,6,'https://images.unsplash.com/photo-1563379091339-03246963d96c?auto=format&fit=crop&w=900&q=85'),
            ('Daily Crust Cafe','Ottapalam Junction','987654321003','Fresh bakery combo','Bakery',100,49,5,'https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=900&q=85'),
            ('Spice Route','Palakkad Bypass','987654321004','Paneer wrap','Snacks',130,79,7,'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=900&q=85'),
            ('Morning Tiffin House','Near Bus Stand','987654321005','Idli & dosa pack','Breakfast',80,39,10,'https://images.unsplash.com/photo-1589301760014-d929f3979dbc?auto=format&fit=crop&w=900&q=85'),
            ('Green Leaf Kitchen','Ottapalam Main Road','987654321001','Veg fried rice','Rice & Biryani',140,79,4,'https://images.unsplash.com/photo-1603133872878-684f208fb84b?auto=format&fit=crop&w=900&q=85'),
        ]
        for i, item in enumerate(demo):
            hname, address, fssai, name, category, old, new, qty, image = item
            email = f'demo{i}@dealdish.local'
            u = User.query.filter_by(email=email).first()
            if not u:
                u = User(name=hname, email=email, password_hash=generate_password_hash('Demo@123'), role='hotel')
                db.session.add(u); db.session.flush()
                h = Hotel(user_id=u.id, name=hname, address=address, fssai=fssai, status='approved', description='Freshly prepared food from a verified local kitchen.')
                db.session.add(h); db.session.flush()
            else: h = Hotel.query.filter_by(user_id=u.id).first()
            db.session.add(Deal(hotel_id=h.id, name=name, category=category, description='A limited-time surplus-food deal. Prepared by the restaurant and available while stocks last.', original_price=old, deal_price=new, quantity=qty, image_url=image, available_from=datetime.utcnow()-timedelta(minutes=5), expires_at=datetime.utcnow()+timedelta(hours=5+i)))
        db.session.commit()

@app.errorhandler(413)
def file_too_large(error):
    flash('The selected image is too large. Please choose an image smaller than 5 MB.', 'danger')
    return redirect(url_for('hotel_new_deal'))


@app.context_processor
def inject_globals():
    user = current_user()
    return {'current_user': user, 'unread_count': Notice.query.filter_by(user_id=user.id, read=False).count() if user else 0, 'now': datetime.utcnow()}

@app.template_filter('money')
def money(value): return '₹{:,.0f}'.format(value or 0)
@app.template_filter('dt')
def dt(value): return value.strftime('%d %b, %I:%M %p') if value else '—'

@app.route('/')
def index():
    q = request.args.get('q','').strip()
    category = request.args.get('category','').strip()
    deals = Deal.query.join(Hotel).filter(Hotel.status=='approved', Deal.active.is_(True), Deal.quantity>0, Deal.expires_at>datetime.utcnow())
    if q: deals = deals.filter(db.or_(Deal.name.ilike(f'%{q}%'), Hotel.name.ilike(f'%{q}%'), Deal.description.ilike(f'%{q}%')))
    if category: deals = deals.filter(Deal.category==category)
    deals = deals.order_by(Deal.expires_at.asc()).all()
    categories = sorted({d.category for d in Deal.query.all()})
    return render_template('index.html', deals=deals, categories=categories, q=q, category=category)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); phone=request.form.get('phone','').strip(); password=request.form.get('password',''); role=request.form.get('role','customer')
        if role not in ('customer','hotel'): role='customer'
        if not name or not email or len(password)<8:
            flash('Enter your name, a valid email and a password of at least 8 characters.','danger')
        elif not re.fullmatch(r'[6-9]\d{9}', phone):
            flash('Enter a valid 10-digit Indian mobile number starting with 6, 7, 8 or 9.','danger')
        elif User.query.filter_by(email=email).first(): flash('An account with this email already exists.','danger')
        elif role=='hotel' and (not re.fullmatch(r'\d{12}', request.form.get('fssai',''))): flash('FSSAI registration number must contain exactly 12 digits.','danger')
        else:
            u=User(name=name,email=email,phone=phone,password_hash=generate_password_hash(password),role=role); db.session.add(u); db.session.flush()
            if role=='hotel':
                db.session.add(Hotel(user_id=u.id,name=request.form.get('hotel_name','').strip() or name,address=request.form.get('address','').strip(),fssai=request.form.get('fssai',''),description=request.form.get('description','').strip(),closing_time=request.form.get('closing_time','22:00'),status='pending'))
                for admin in User.query.filter_by(role='admin').all(): notify(admin.id, f'New hotel verification request: {u.name}.')
                flash('Hotel account created. Your FSSAI details are pending admin review; listings unlock after approval.','success')
            else: flash('Account created successfully. Welcome to DealDish!','success')
            db.session.commit(); session['user_id']=u.id
            return redirect(url_for('hotel_dashboard' if role=='hotel' else 'index'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        u=User.query.filter_by(email=email).first()
        if u and check_password_hash(u.password_hash,password):
            session.clear(); session['user_id']=u.id
            nxt=request.args.get('next')
            if nxt and nxt.startswith('/'): return redirect(nxt)
            return redirect(url_for({'admin':'admin_dashboard','hotel':'hotel_dashboard'}.get(u.role,'index')))
        flash('Email or password is incorrect.','danger')
    return render_template('login.html')

@app.route('/logout')
def logout(): session.clear(); flash('You have been signed out.','success'); return redirect(url_for('index'))

@app.route('/deal/<int:deal_id>')
def deal_detail(deal_id):
    deal=Deal.query.get_or_404(deal_id)
    reviews=Review.query.filter_by(deal_id=deal.id).order_by(Review.created_at.desc()).all()
    return render_template('deal_detail.html', deal=deal, reviews=reviews, live=is_live(deal), food_average=round(sum(r.rating for r in reviews)/len(reviews),1) if reviews else None, hotel_average=round(sum(r.hotel_rating for r in Review.query.join(Deal).filter(Deal.hotel_id==deal.hotel_id).all())/len(Review.query.join(Deal).filter(Deal.hotel_id==deal.hotel_id).all()),1) if Review.query.join(Deal).filter(Deal.hotel_id==deal.hotel_id).count() else None)

@app.route('/cart')
@login_required
def cart():
    items=[]
    for key, qty in session.get('cart',{}).items():
        deal=Deal.query.get(int(key))
        if deal and is_live(deal): items.append({'deal':deal,'qty':int(qty)})
    return render_template('cart.html', items=items, total=sum(x['deal'].deal_price*x['qty'] for x in items))

@app.route('/cart/add/<int:deal_id>', methods=['POST'])
@login_required
def cart_add(deal_id):
    deal=Deal.query.get_or_404(deal_id)
    if current_user().role!='customer': flash('Only customer accounts can order deals.','warning')
    elif not is_live(deal): flash('This deal has expired or sold out.','danger')
    else:
        cart=session.get('cart',{}); key=str(deal.id); qty=int(request.form.get('quantity',1))
        if qty<1 or qty>deal.quantity: flash('Please choose a quantity currently available.','danger')
        else: cart[key]=min(int(cart.get(key,0))+qty,deal.quantity); session['cart']=cart; session.modified=True; flash('Added to your basket.','success')
    return redirect(request.referrer or url_for('index'))

@app.route('/cart/remove/<int:deal_id>', methods=['POST'])
@login_required
def cart_remove(deal_id):
    cart=session.get('cart',{}); cart.pop(str(deal_id),None); session['cart']=cart; session.modified=True; return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET','POST'])
@login_required
def checkout():
    if current_user().role!='customer': flash('Please use a customer account to checkout.','warning'); return redirect(url_for('index'))
    cart=session.get('cart',{}); items=[]
    for key,qty in cart.items():
        d=Deal.query.get(int(key))
        if d and is_live(d) and int(qty)<=d.quantity: items.append((d,int(qty)))
    if not items: flash('Your basket is empty or a deal is no longer available.','warning'); return redirect(url_for('cart'))
    if request.method=='POST':
        fulfilment=request.form.get('fulfilment','Pickup'); payment=request.form.get('payment','Cash on pickup')
        if fulfilment not in ('Pickup','Delivery') or payment not in ('Cash on pickup','Cash on delivery','Online payment (demo)'):
            flash('Choose valid fulfilment and payment options.','danger'); return redirect(url_for('checkout'))
        if fulfilment=='Delivery' and not request.form.get('delivery_address','').strip(): flash('Enter a delivery address.','danger'); return redirect(url_for('checkout'))
        # Re-check stock and expiry before committing the entire checkout.
        if any(not is_live(d) or qty>d.quantity for d,qty in items): flash('A deal changed while you were checking out. Please review your basket.','danger'); return redirect(url_for('cart'))
        for d,qty in items:
            d.quantity-=qty
            o=Order(user_id=current_user().id,deal_id=d.id,quantity=qty,total=d.deal_price*qty,fulfilment=fulfilment,payment=payment,status='Placed',reservation_expires=datetime.utcnow()+timedelta(minutes=15))
            db.session.add(o); db.session.flush()
            notify(d.hotel.user_id, f'New order #{o.id}: {qty} × {d.name}.')
            notify(current_user().id, f'Order #{o.id} placed. Please {"collect it" if fulfilment=="Pickup" else "watch for delivery updates"}.')
        current_user().coins += max(1, int(sum(d.deal_price*qty for d,qty in items)//50))
        db.session.commit(); session['cart']={}; flash('Order placed! Reward points have been added to your account.','success'); return redirect(url_for('my_orders'))
    return render_template('checkout.html', items=items,total=sum(d.deal_price*q for d,q in items))

@app.route('/orders')
@login_required
def my_orders():
    user=current_user()
    if user.role=='hotel': return redirect(url_for('hotel_orders'))
    orders=Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    return render_template('orders.html', orders=orders)

@app.route('/order/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if current_user().role != 'customer' or order.user_id != current_user().id:
        flash('You cannot cancel this order.', 'danger')
        return redirect(url_for('my_orders'))
    if order.status not in ('Placed', 'Confirmed'):
        flash('This order can no longer be cancelled because preparation or fulfilment has started.', 'warning')
        return redirect(url_for('my_orders'))
    reason = request.form.get('reason', '').strip()[:300]
    order.status = 'Cancelled'
    order.cancellation_reason = reason or 'Cancelled by customer'
    order.cancelled_at = datetime.utcnow()
    order.deal.quantity += order.quantity
    if 'online' in (order.payment or '').lower():
        order.refund_status = 'Pending manual refund'
        order.refund_amount = order.total
    else:
        order.refund_status = 'Not applicable - cash payment'
        order.refund_amount = 0
    notify(order.deal.hotel.user_id, f'Order #{order.id} was cancelled by the customer. Stock has been restored.')
    notify(order.user_id, f'Order #{order.id} has been cancelled. Refund status: {order.refund_status}.')
    db.session.commit()
    flash('Order cancelled. ' + ('Your refund is pending admin processing.' if order.refund_amount else 'No online refund is due.'), 'success')
    return redirect(url_for('my_orders'))

@app.route('/order/<int:order_id>/review', methods=['POST'])
@login_required
def review_order(order_id):
    o=Order.query.get_or_404(order_id)
    if o.user_id!=current_user().id or o.status not in ('Completed','Collected','Delivered'):
        flash('You can review an order after it is completed.','warning'); return redirect(url_for('my_orders'))
    if Review.query.filter_by(order_id=o.id).first(): flash('You have already reviewed this order.','info')
    else:
        rating=max(1,min(5,int(request.form.get('food_rating',request.form.get('rating',5))))); hotel_rating=max(1,min(5,int(request.form.get('hotel_rating',5)))); comment=request.form.get('comment','').strip()[:500]
        db.session.add(Review(user_id=current_user().id,deal_id=o.deal_id,order_id=o.id,rating=rating,hotel_rating=hotel_rating,comment=comment)); notify(o.deal.hotel.user_id,f'New customer feedback: food {rating}/5, hotel {hotel_rating}/5.'); db.session.commit(); flash('Thanks for sharing your feedback!','success')
    return redirect(url_for('my_orders'))

@app.route('/notifications')
@login_required
def notifications():
    notices=Notice.query.filter_by(user_id=current_user().id).order_by(Notice.created_at.desc()).all()
    for n in notices: n.read=True
    db.session.commit(); return render_template('notifications.html',notices=notices)

@app.route('/hotel/dashboard')
@roles_required('hotel')
def hotel_dashboard():
    h=current_user().hotel_profile
    if not h: flash('Hotel profile not found.','danger'); return redirect(url_for('index'))
    deals=Deal.query.filter_by(hotel_id=h.id).order_by(Deal.expires_at.asc()).all()
    orders=Order.query.join(Deal).filter(Deal.hotel_id==h.id).order_by(Order.created_at.desc()).limit(8).all()
    reviews=Review.query.join(Deal).filter(Deal.hotel_id==h.id).order_by(Review.created_at.desc()).limit(30).all()
    return render_template('hotel_dashboard.html',hotel=h,deals=deals,orders=orders,reviews=reviews)

@app.route('/hotel/location', methods=['POST'])
@roles_required('hotel')
def hotel_update_location():
    hotel = current_user().hotel_profile
    if not hotel:
        flash('Hotel profile not found.', 'danger')
        return redirect(url_for('index'))

    try:
        lat = float(request.form.get('lat', ''))
        lng = float(request.form.get('lng', ''))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError()
    except (TypeError, ValueError):
        flash('Please capture a valid business location.', 'danger')
        return redirect(url_for('hotel_dashboard'))

    hotel.lat = lat
    hotel.lng = lng
    db.session.commit()
    flash('Your business location has been saved. Nearby customers can now discover your deals.', 'success')
    return redirect(url_for('hotel_dashboard'))


@app.route('/hotel/deals/new', methods=['GET', 'POST'])
@roles_required('hotel')
def hotel_new_deal():
    h = current_user().hotel_profile
    if not h:
        flash('Hotel profile not found.', 'danger')
        return redirect(url_for('hotel_dashboard'))
    if h.status != 'approved':
        flash('Your hotel must be approved before publishing deals.', 'warning')
        return redirect(url_for('hotel_dashboard'))

    if request.method == 'POST':
        image_file = request.files.get('image')
        saved_image_path = None
        try:
            name = request.form.get('name', '').strip()
            category = request.form.get('category', '').strip()
            original = float(request.form.get('original_price', ''))
            price = float(request.form.get('deal_price', ''))
            qty = int(request.form.get('quantity', ''))
            expires = datetime.strptime(request.form.get('expires_at', ''), '%Y-%m-%dT%H:%M')

            if (not name or not category or original <= 0 or price <= 0
                    or price >= original or qty < 1 or expires <= datetime.utcnow()):
                raise ValueError('Please check the deal details.')
            if datetime.utcnow().hour < 23 and expires > datetime.utcnow() + timedelta(days=2):
                raise ValueError('Expiry must be within the allowed deal period.')

            if not image_file or not image_file.filename:
                flash('Please choose a food photo or capture one before publishing.', 'danger')
                return render_template(
                    'hotel_new_deal.html',
                    default_expiry=(datetime.now() + timedelta(hours=4)).strftime('%Y-%m-%dT%H:%M')
                )

            original_filename = secure_filename(image_file.filename)
            extension = original_filename.rsplit('.', 1)[-1].lower() if '.' in original_filename else ''
            if extension not in ALLOWED_IMAGE_EXTENSIONS:
                flash('Please upload a JPG, JPEG, PNG or WEBP image.', 'danger')
                return render_template(
                    'hotel_new_deal.html',
                    default_expiry=(datetime.now() + timedelta(hours=4)).strftime('%Y-%m-%dT%H:%M')
                )

            unique_filename = f'{uuid.uuid4().hex}.{extension}'
            saved_image_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            image_file.save(saved_image_path)
            image_url = url_for('static', filename=f'uploads/{unique_filename}')

            deal = Deal(
                hotel_id=h.id,
                name=name,
                category=category,
                description=request.form.get('description', '').strip(),
                original_price=original,
                deal_price=price,
                quantity=qty,
                image_url=image_url,
                available_from=datetime.utcnow(),
                expires_at=expires
            )
            db.session.add(deal)
            db.session.commit()
            flash('Your surplus deal is now live.', 'success')
            return redirect(url_for('hotel_dashboard'))

        except (ValueError, KeyError):
            if saved_image_path and os.path.exists(saved_image_path):
                os.remove(saved_image_path)
            flash('Check the deal details. The deal price must be lower than the original price, quantity must be at least 1, and expiry must be in the future.', 'danger')

    return render_template(
        'hotel_new_deal.html',
        default_expiry=(datetime.now() + timedelta(hours=4)).strftime('%Y-%m-%dT%H:%M')
    )

@app.route('/hotel/deal/<int:deal_id>/toggle', methods=['POST'])
@roles_required('hotel')
def hotel_toggle_deal(deal_id):
    d=Deal.query.get_or_404(deal_id)
    if d.hotel.user_id!=current_user().id: flash('Not your deal.','danger')
    else: d.active=not d.active; db.session.commit(); flash('Deal visibility updated.','success')
    return redirect(url_for('hotel_dashboard'))

@app.route('/hotel/orders')
@roles_required('hotel')
def hotel_orders():
    h=current_user().hotel_profile
    orders=Order.query.join(Deal).filter(Deal.hotel_id==h.id).order_by(Order.created_at.desc()).all()
    return render_template('hotel_orders.html',orders=orders)

@app.route('/hotel/order/<int:order_id>/status', methods=['POST'])
@roles_required('hotel')
def hotel_order_status(order_id):
    o=Order.query.get_or_404(order_id)
    if o.deal.hotel.user_id!=current_user().id: flash('Not your order.','danger')
    else:
        status=request.form.get('status')
        allowed=('Confirmed','Preparing','Ready for pickup','Out for delivery','Completed','Collected','Delivered','Cancelled')
        if status in allowed and o.status != 'Cancelled':
            if status == 'Cancelled':
                if o.status in ('Completed','Collected','Delivered'):
                    flash('Completed orders cannot be cancelled.', 'warning')
                    return redirect(request.referrer or url_for('hotel_orders'))
                o.deal.quantity += o.quantity
                o.cancelled_at = datetime.utcnow()
                o.cancellation_reason = 'Cancelled by hotel'
                if 'online' in (o.payment or '').lower():
                    o.refund_status = 'Pending manual refund'; o.refund_amount = o.total
                else:
                    o.refund_status = 'Not applicable - cash payment'; o.refund_amount = 0
            o.status=status
            notify(o.user_id,f'Order #{o.id} status updated: {status}.' + (f' Refund status: {o.refund_status}.' if status=='Cancelled' else ''))
            db.session.commit(); flash('Order status updated.','success')
        elif o.status == 'Cancelled': flash('This order is already cancelled.', 'info')
    return redirect(request.referrer or url_for('hotel_orders'))

@app.route('/admin')
@roles_required('admin')
def admin_dashboard():
    return render_template('admin_dashboard.html', users=User.query.order_by(User.created_at.desc()).all(), hotels=Hotel.query.order_by(Hotel.id.desc()).all(), deals=Deal.query.order_by(Deal.id.desc()).all(), orders=Order.query.order_by(Order.created_at.desc()).all(), pending=Hotel.query.filter_by(status='pending').count())

@app.route('/admin/hotel/<int:hotel_id>/review', methods=['POST'])
@roles_required('admin')
def admin_review_hotel(hotel_id):
    h=Hotel.query.get_or_404(hotel_id); status=request.form.get('status')
    if status in ('approved','rejected'):
        h.status=status; h.admin_note=request.form.get('note','').strip()[:300]; notify(h.user_id,f'Your DealDish hotel application was {status}.' + (f' Note: {h.admin_note}' if h.admin_note else '')); db.session.commit(); flash(f'{h.name} marked {status}.','success')
    return redirect(url_for('admin_dashboard')+'#hotels')

@app.route('/admin/order/<int:order_id>/refund', methods=['POST'])
@roles_required('admin')
def admin_mark_refunded(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status != 'Cancelled' or order.refund_status != 'Pending manual refund':
        flash('This order is not awaiting a refund.', 'warning')
    else:
        order.refund_status = 'Refund marked as processed'
        notify(order.user_id, f'Refund for cancelled order #{order.id} has been marked as processed by DealDish admin.')
        db.session.commit()
        flash('Refund marked as processed. Complete the actual transfer through your payment provider.', 'success')
    return redirect(url_for('admin_dashboard') + '#orders')

@app.route('/admin/deal/<int:deal_id>/toggle', methods=['POST'])
@roles_required('admin')
def admin_toggle_deal(deal_id):
    d=Deal.query.get_or_404(deal_id); d.active=not d.active; db.session.commit(); flash('Deal moderation updated.','success'); return redirect(url_for('admin_dashboard')+'#deals')

@app.route('/api/nearby-deals')
def nearby_deals():
    try:
        lat = float(request.args['lat'])
        lng = float(request.args['lng'])
        radius = float(request.args.get('radius', 10))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError()
        if not (0 < radius <= 100):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        return jsonify({'success': False, 'error': 'Please provide valid latitude, longitude and radius.'}), 400

    results = []
    deals = Deal.query.join(Hotel).filter(
        Hotel.status == 'approved',
        Deal.active.is_(True),
        Deal.quantity > 0,
        Deal.expires_at > datetime.utcnow()
    ).all()

    for deal in deals:
        hotel = deal.hotel
        if hotel.lat is None or hotel.lng is None:
            continue

        lat1, lon1 = math.radians(lat), math.radians(lng)
        lat2, lon2 = math.radians(hotel.lat), math.radians(hotel.lng)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
        distance = 6371 * 2 * math.asin(math.sqrt(a))

        if distance <= radius:
            discount = round(((deal.original_price - deal.deal_price) / deal.original_price) * 100) if deal.original_price else 0
            results.append({
                'id': deal.id,
                'name': deal.name,
                'hotel': hotel.name,
                'price': deal.deal_price,
                'original_price': deal.original_price,
                'discount_percent': discount,
                'distance_km': round(distance, 2),
                'expires_at': deal.expires_at.isoformat(),
                'quantity': deal.quantity,
                'category': deal.category,
                'image_url': deal.image_url or '',
                'deal_url': url_for('deal_detail', deal_id=deal.id)
            })

    results.sort(key=lambda item: item['distance_km'])
    return jsonify({
        'success': True,
        'count': len(results),
        'radius': radius,
        'deals': results
    })

@app.route('/about')
def about(): return render_template('about.html')

with app.app_context():
    db.create_all()
    # Additive SQLite migration: preserve existing DealDish accounts, orders and reviews.
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    order_columns = {c['name'] for c in inspector.get_columns('order')}
    for name, sql in {
        'cancellation_reason': "ALTER TABLE 'order' ADD COLUMN cancellation_reason VARCHAR(300) DEFAULT ''",
        'cancelled_at': "ALTER TABLE 'order' ADD COLUMN cancelled_at DATETIME",
        'refund_status': "ALTER TABLE 'order' ADD COLUMN refund_status VARCHAR(30) DEFAULT 'Not applicable'",
        'refund_amount': "ALTER TABLE 'order' ADD COLUMN refund_amount FLOAT DEFAULT 0"
    }.items():
        if name not in order_columns: db.session.execute(db.text(sql))
    review_columns = {c['name'] for c in inspector.get_columns('review')}
    if 'hotel_rating' not in review_columns:
        db.session.execute(db.text('ALTER TABLE review ADD COLUMN hotel_rating INTEGER NOT NULL DEFAULT 5'))
    db.session.commit()
    seed_data()

if __name__ == '__main__': app.run(debug=True)
