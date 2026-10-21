# 1. IMPORTACIONES
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import socket

app = Flask(__name__)
app.secret_key = 'clave_secreta_vetsystem_segura'

# 2. CONEXIÓN A BASE DE DATOS A TRAVÉS DE HAPROXY
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.10:3306/vet_clinic_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# SOLUCIÓN AL ERROR 2013: Configuraciones para evitar que MySQL cierre la conexión por inactividad
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 20
app.config['SQLALCHEMY_POOL_PRE_PING'] = True

db = SQLAlchemy(app)

# 3. MODELOS (Tablas)
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class Owner(db.Model):
    __tablename__ = 'owners'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(255))

class Pet(db.Model):
    __tablename__ = 'pets'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id')) # Enlaza al dueño
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(50))
    breed = db.Column(db.String(50))
    age = db.Column(db.Integer)
    weight = db.Column(db.Numeric(5, 2))

class Consultation(db.Model):
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    pet_id = db.Column(db.Integer, db.ForeignKey('pets.id')) # Enlaza a la mascota
    reason = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    consultation_date = db.Column(db.DateTime, server_default=db.func.now())

# 4. CREACIÓN DEL USUARIO ADMIN (Si no existe)
with app.app_context():
    try:
        db.create_all()
        if not User.query.filter_by(username='emerson_7').first():
            admin_user = User(username='emerson_7', password_hash=generate_password_hash('P@ssw0rd'), role='admin')
            db.session.add(admin_user)
            db.session.commit()
    except Exception as e:
        print(f"Error al crear usuario inicial: {e}")

# 5. SEGURIDAD: Decorador para proteger rutas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión primero.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 6. RUTAS
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                return redirect(url_for('inicio'))
            else:
                flash('Usuario o contraseña incorrectos', 'danger')
        except Exception:
            flash('Error de conexión a la base de datos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('inicio'))

@app.route('/inicio')
@login_required
def inicio():
    try:
        total_pacientes = Pet.query.count()
        total_duenos = Owner.query.count()
    except Exception:
        total_pacientes = 0
        total_duenos = 0
    return render_template('inicio.html', hostname=socket.gethostname(), total_pacientes=total_pacientes, total_duenos=total_duenos)

@app.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar_paciente():
    if request.method == 'POST':
        try:
            owner = Owner(name=request.form['owner_name'], phone=request.form.get('owner_phone'), email=request.form.get('owner_email'), address=request.form.get('owner_address'))
            db.session.add(owner)
            db.session.flush() # Obtiene el ID del dueño
            
            # SOLUCIÓN AL ERROR 500: "or None" evita que campos vacíos rompan la BD
            pet = Pet(owner_id=owner.id, name=request.form['pet_name'], species=request.form.get('pet_species'), breed=request.form.get('pet_breed'), age=request.form.get('pet_age') or None, weight=request.form.get('pet_weight') or None)
            db.session.add(pet)
            db.session.commit()
            flash('Paciente registrado exitosamente!', 'success')
            return redirect(url_for('pacientes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar: {str(e)}', 'danger')
    return render_template('index.html', hostname=socket.gethostname())

@app.route('/pacientes')
@login_required
def pacientes():
    try:
        lista = db.session.query(Pet, Owner).join(Owner, Pet.owner_id == Owner.id).all()
    except Exception:
        lista = []
    return render_template('pacientes.html', pacientes=lista, hostname=socket.gethostname())

@app.route('/paciente/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_paciente(id):
    pet = Pet.query.get_or_404(id)
    owner = Owner.query.get(pet.owner_id)
    
    if request.method == 'POST':
        try:
            owner.name = request.form['owner_name']
            owner.phone = request.form.get('owner_phone')
            owner.email = request.form.get('owner_email')
            owner.address = request.form.get('owner_address')
            
            pet.name = request.form['pet_name']
            pet.species = request.form.get('pet_species')
            pet.breed = request.form.get('pet_breed')
            # SOLUCIÓN AL ERROR 500 AL EDITAR: Se usa "or None" por si dejan los campos vacíos
            pet.age = request.form.get('pet_age') or None
            pet.weight = request.form.get('pet_weight') or None
            
            db.session.commit()
            flash('Paciente actualizado correctamente!', 'success')
            return redirect(url_for('pacientes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'danger')
            
    return render_template('editar_paciente.html', pet=pet, owner=owner, hostname=socket.gethostname())

@app.route('/paciente/eliminar/<int:id>')
@login_required
def eliminar_paciente(id):
    if session.get('role') not in ['admin', 'sistemas']:
        flash('No tienes permiso para eliminar.', 'danger')
        return redirect(url_for('pacientes'))
    try:
        pet = Pet.query.get_or_404(id)
        owner = Owner.query.get(pet.owner_id)
        
        # SOLUCIÓN AL ERROR DE LLAVE FORÁNEA:
        # 1. Borra las consultas asociadas
        Consultation.query.filter_by(pet_id=pet.id).delete()
        
        # 2. El comando flush() fuerza a la BD a aplicar el borrado de consultas inmediatamente
        db.session.flush()
        
        # 3. Ahora sí, borra la mascota
        db.session.delete(pet)
        db.session.flush()
        
        # 4. Finalmente borra al dueño
        db.session.delete(owner)
        
        db.session.commit()
        flash('Paciente eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'danger')
    return redirect(url_for('pacientes'))

@app.route('/usuarios', methods=['GET', 'POST'])
@login_required
def usuarios():
    if session.get('role') not in ['admin', 'sistemas']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        try:
            username = request.form['username']
            password = request.form['password']
            role = request.form['role']
            hashed_pw = generate_password_hash(password)
            nuevo_user = User(username=username, password_hash=hashed_pw, role=role)
            db.session.add(nuevo_user)
            db.session.commit()
            flash('Usuario creado exitosamente!', 'success')
        except Exception:
            db.session.rollback()
            flash('Error al crear el usuario (quizás ya existe).', 'danger')
    
    try:
        lista_users = User.query.all()
    except Exception:
        lista_users = []
    return render_template('usuarios.html', usuarios=lista_users, hostname=socket.gethostname())

@app.route('/usuario/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    if session.get('role') not in ['admin', 'sistemas']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('usuarios'))

    user = User.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            user.username = request.form['username']
            user.role = request.form['role']
            
            # Solo actualiza la contraseña si el usuario escribió una nueva
            new_password = request.form.get('password')
            if new_password:
                user.password_hash = generate_password_hash(new_password)
                
            db.session.commit()
            flash('Usuario actualizado correctamente!', 'success')
            return redirect(url_for('usuarios'))
        except Exception:
            db.session.rollback()
            flash('Error al actualizar el usuario.', 'danger')
            
    return render_template('editar_usuario.html', user=user, hostname=socket.gethostname())

@app.route('/usuario/eliminar/<int:id>')
@login_required
def eliminar_usuario(id):
    if session.get('role') not in ['admin', 'sistemas']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('usuarios'))

    # Protección para no eliminarse a sí mismo
    if id == session.get('user_id'):
        flash('No puedes eliminar tu propio usuario activo.', 'warning')
        return redirect(url_for('usuarios'))

    try:
        user = User.query.get_or_404(id)
        db.session.delete(user)
        db.session.commit()
        flash('Usuario eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el usuario: {str(e)}', 'danger')

    return redirect(url_for('usuarios'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False) # debug=False para producción
