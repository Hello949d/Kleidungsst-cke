# app.py

import os
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
import pandas as pd

# --- App-Konfiguration und Modelle (unverändert) ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'eine-sehr-geheime-zeichenkette-fuer-sessions'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance/database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Bitte melde dich an."
login_manager.login_message_category = "warning"

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True) 
    role = db.Column(db.String(20), nullable=False, default='user')
    bekleidungsnummer = db.Column(db.String(20), unique=True, nullable=False)
    auswahlen = db.relationship('Auswahl', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password) if self.password_hash else False

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    subcategories = db.relationship('Category', backref=db.backref('parent', remote_side=[id]), lazy='dynamic', cascade="all, delete-orphan")
    products = db.relationship('Product', backref='category', lazy='dynamic')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    groesse = db.Column(db.String(20), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    auswahlen = db.relationship('Auswahl', backref='product', lazy='dynamic', cascade="all, delete-orphan")

class Auswahl(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    menge = db.Column(db.Integer, nullable=False, default=1)
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='_user_product_uc'),)

@login_manager.user_loader
def load_user(user_id): return db.session.get(User, int(user_id))

# --- Kern-Routen (unverändert) ---
@app.route('/')
def index():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and ((user.role == 'admin' and user.check_password(request.form.get('identifier'))) or \
                     (user.role == 'user' and user.bekleidungsnummer == request.form.get('identifier'))):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Ungültiger Username oder Kennung.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username, bekleidungsnummer = request.form.get('username'), request.form.get('bekleidungsnummer')
        if User.query.filter_by(username=username).first() or User.query.filter_by(bekleidungsnummer=bekleidungsnummer).first():
            flash('Username oder Bekleidungsnummer bereits vergeben.', 'danger')
        else:
            db.session.add(User(username=username, bekleidungsnummer=bekleidungsnummer, role='user'))
            db.session.commit()
            flash('Registrierung erfolgreich!', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        top_level_categories = Category.query.filter_by(parent_id=None).order_by(Category.name).all()
        unassigned_products = Product.query.filter_by(category_id=None).order_by(Product.name).all()
        all_users_with_selections = User.query.filter_by(role='user').order_by(User.username).all()
        product_summary = db.session.query(
            Product.name, Product.groesse, func.sum(Auswahl.menge).label('total_menge')
        ).join(Auswahl, isouter=True).group_by(Product.id).order_by(Product.name).all()
        return render_template('admin_dashboard_dragdrop.html', 
                               categories=top_level_categories, unassigned_products=unassigned_products,
                               all_users=all_users_with_selections, product_summary=product_summary,
                               Category=Category, Product=Product)
    else:
        categories = Category.query.filter_by(parent_id=None).order_by(Category.name).all()
        user_mengen = {a.product_id: a.menge for a in current_user.auswahlen}
        return render_template('user_dashboard.html', categories=categories, user_mengen=user_mengen,
                               Category=Category, Product=Product)

# --- Admin-Routen (Löschen, Hinzufügen) ---
@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if current_user.role != 'admin': return redirect(url_for('dashboard'))
    product_to_delete = db.session.get(Product, product_id)
    if product_to_delete:
        db.session.delete(product_to_delete)
        db.session.commit()
        flash(f'Produkt "{product_to_delete.name}" wurde gelöscht.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/admin/category/delete/<int:category_id>', methods=['POST'])
@login_required
def delete_category(category_id):
    if current_user.role != 'admin': return redirect(url_for('dashboard'))
    category_to_delete = db.session.get(Category, category_id)
    if category_to_delete:
        for product in category_to_delete.products: product.category_id = None
        for subcategory in category_to_delete.subcategories: subcategory.parent_id = None
        db.session.delete(category_to_delete)
        db.session.commit()
        flash(f'Ordner "{category_to_delete.name}" wurde gelöscht.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/admin/category/add', methods=['POST'])
@login_required
def add_category():
    if current_user.role != 'admin': return redirect(url_for('dashboard'))
    name = request.form.get('name')
    if name:
        db.session.add(Category(name=name, parent_id=None))
        db.session.commit()
        flash('Ordner erfolgreich erstellt.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/admin/import_excel', methods=['POST'])
@login_required
def import_excel():
    if current_user.role != 'admin': return redirect(url_for('dashboard'))
    file = request.files.get('excel_file')
    if not file or not file.filename.endswith(('.xlsx', '.xls')):
        flash('Bitte eine gültige Excel-Datei hochladen.', 'danger')
        return redirect(url_for('dashboard'))
    try:
        df = pd.read_excel(file, header=None)
        for _, row in df.iterrows():
            name, groesse = (str(row[0]), str(row[1])) if pd.notna(row[0]) and pd.notna(row[1]) else (None, None)
            if name and groesse: db.session.add(Product(name=name, groesse=groesse, category_id=None))
        db.session.commit()
        flash(f'{len(df)} Produktzeilen verarbeitet.', 'success')
    except Exception as e: flash(f'Fehler beim Import: {e}', 'danger')
    return redirect(url_for('dashboard'))

# --- API-Routen ---

# NEU: API-Endpunkt für das Verschieben MEHRERER Produkte
@app.route('/admin/api/products/move', methods=['POST'])
@login_required
def move_products():
    if current_user.role != 'admin': return jsonify({'success': False}), 403
    
    data = request.get_json()
    product_ids = data.get('productIds', [])
    new_category_id = data.get('newCategoryId') or None

    if not product_ids:
        return jsonify({'success': False, 'message': 'Keine Produkte ausgewählt.'}), 400

    # Effizientes Update für alle Produkte in der Liste
    Product.query.filter(Product.id.in_(product_ids)).update({'category_id': new_category_id}, synchronize_session=False)
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'{len(product_ids)} Produkte verschoben.'})

@app.route('/admin/api/category/move', methods=['POST'])
@login_required
def move_category():
    if current_user.role != 'admin': return jsonify({'success': False}), 403
    data = request.get_json()
    category = db.session.get(Category, data.get('categoryId'))
    if category:
        category.parent_id = data.get('newParentId') or None
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

# --- User-Route (unverändert) ---
@app.route('/user/select', methods=['POST'])
@login_required
def user_select():
    if current_user.role != 'user': return redirect(url_for('dashboard'))
    for key, value in request.form.items():
        if key.startswith('menge_'):
            pid, menge = int(key.split('_')[1]), int(value or 0)
            existing = Auswahl.query.filter_by(user_id=current_user.id, product_id=pid).first()
            if menge > 0:
                if existing: existing.menge = menge
                else: db.session.add(Auswahl(user_id=current_user.id, product_id=pid, menge=menge))
            elif existing: db.session.delete(existing)
    db.session.commit()
    flash('Auswahl gespeichert!', 'success')
    return redirect(url_for('dashboard'))

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='Admin').first():
            admin_user = User(username='Admin', role='admin', bekleidungsnummer='ADMIN')
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("Admin-Benutzer erstellt.")
        print("Datenbank initialisiert.")

if __name__ == '__main__':
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
    if not os.path.exists(instance_path): os.makedirs(instance_path)
    init_db()
    app.run(debug=True)