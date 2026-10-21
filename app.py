# ==============================================================================
# IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import socket

# ==============================================================================
# CONFIGURACIÓN INICIAL
# ==============================================================================
app = Flask(__name__)
app.secret_key = 'clave_secreta_vetsystem_segura' # Clave para que funcionen los mensajes flash y las sesiones

# Conexión a MySQL A TRAVÉS DE HAPROXY (192.168.56.10). 
# Si db-01 se cae, HAProxy redirige a db-02 automáticamente.
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.10:3306/vet_clinic_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- SOLUCIÓN AL ERROR DE CONEXIÓN (2013) ---
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280      # Recicla conexiones viejas
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 20       # Espera máxima de conexión
app.config['SQLALCHEMY_POOL_PRE_PING'] = True    # Hace "ping" antes de conectar, si está muerta, reconecta.

db = SQLAlchemy(app)

# ==============================================================================
# MODELOS (TABLAS)
# ==============================================================================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False) # unique=True evita duplicados
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
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id')) # Relación con Dueño
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(50))
    breed = db.Column(db.String(50))
    age = db.Column(db.Integer)
    weight = db.Column(db.Numeric(5, 2))

class Consultation(db.Model):
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    pet_id = db.Column(db.Integer, db.ForeignKey('pets.id')) # Relación con Mascota
    reason = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    consultation_date = db.Column(db.DateTime, server_default=db.func.now())

# ==============================================================================
# CREACIÓN AUTOMÁTICA DEL ADMINISTRADOR
# ==============================================================================
# Al arrancar la app, verifica si emerson_7 existe. Si no, lo crea.
with app.app_context():
    try:
        db.create_all()
        if not User.query.filter_by(username='emerson_7').first():
            admin_user = User(username='emerson_7', password_hash=generate_password_hash('P@ssw0rd'), role='admin')
            db.session.add(admin_user)
            db.session.commit()
    except Exception as e:
        print(f"Error al crear usuario inicial: {e}")

# ==============================================================================
# DECORADOR DE SEGURIDAD (Requiere Login)
# ==============================================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión primero.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# RUTAS (CONTROLADORES)
# ==============================================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            user = User.query.filter_by(username=username).first()
            # Compara la contraseña encriptada
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
    session.clear() # Borra la sesión para salir
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('inicio'))

@app.route('/inicio')
@login_required
def inicio():
    try:
        # Cuenta los registros para mostrarlos en las tarjetas del panel
        total_pacientes = Pet.query.count()
        total_duenos = Owner.query.count()
        total_consultas = Consultation.query.count() # <--- SE AGREGÓ ESTO PARA EL CONTADOR
    except Exception:
        # Si falla la BD, muestra 0 en lugar de romper la página
        total_pacientes = 0
        total_duenos = 0
        total_consultas = 0
    return render_template('inicio.html', hostname=socket.gethostname(), total_pacientes=total_pacientes, total_duenos=total_duenos, total_consultas=total_consultas)

@app.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar_paciente():
    if request.method == 'POST':
        try:
            # 1. Guarda al Dueño
            owner = Owner(name=request.form['owner_name'], phone=request.form.get('owner_phone'), email=request.form.get('owner_email'), address=request.form.get('owner_address'))
            db.session.add(owner)
            db.session.flush() # Obtiene el ID del dueño
            
            # 2. Guarda la Mascota
            age = request.form.get('pet_age')
            weight = request.form.get('pet_weight')
            
            # CONVERSIÓN: Evita el error 500 si los campos numéricos se dejan en blanco
            pet = Pet(owner_id=owner.id, name=request.form['pet_name'], species=request.form.get('pet_species'), breed=request.form.get('pet_breed'), age=int(age) if age else None, weight=float(weight) if weight else None)
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
        # Hace un JOIN entre Mascota y Dueño para mostrar la info en la tabla
        lista = db.session.query(Pet, Owner).join(Owner, Pet.owner_id == Owner.id).all()
    except Exception:
        lista = []
    return render_template('pacientes.html', pacientes=lista, hostname=socket.gethostname())

@app.route('/paciente/ver/<int:id>')
@login_required
def ver_paciente(id):
    # Busca la mascota, el dueño y TODAS las consultas asociadas
    pet = Pet.query.get_or_404(id)
    owner = Owner.query.get(pet.owner_id)
    consultas = Consultation.query.filter_by(pet_id=pet.id).order_by(Consultation.consultation_date.desc()).all()
    return render_template('ver_paciente.html', pet=pet, owner=owner, consultas=consultas, hostname=socket.gethostname())

@app.route('/paciente/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_paciente(id):
    pet = Pet.query.get_or_404(id)
    owner = Owner.query.get(pet.owner_id)
    
    if request.method == 'POST':
        try:
            # Actualiza los datos del dueño
            owner.name = request.form['owner_name']
            owner.phone = request.form.get('owner_phone')
            owner.email = request.form.get('owner_email')
            owner.address = request.form.get('owner_address')
            
            # Actualiza los datos de la mascota
            pet.name = request.form['pet_name']
            pet.species = request.form.get('pet_species')
            pet.breed = request.form.get('pet_breed')
            
            # CONVERSIÓN SEGURA DE DATOS (Evita el error 500 al editar)
            age = request.form.get('pet_age')
            weight = request.form.get('pet_weight')
            pet.age = int(age) if age else None
            pet.weight = float(weight) if weight else None
            
            db.session.commit()
            flash('Paciente actualizado correctamente!', 'success')
            return redirect(url_for('pacientes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar paciente: {str(e)}', 'danger')
            
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
        
        # SOLUCIÓN AL ERROR 1451: Se borran las consultas (hijas) primero.
        Consultation.query.filter_by(pet_id=pet.id).delete()
        db.session.flush() # Fuerza a la BD a procesar este borrado AHORA
        
        db.session.delete(pet) # Luego borra la mascota
        db.session.flush()
        db.session.delete(owner) # Finalmente borra el dueño
        
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
            nuevo_username = request.form['username']
            
            # SOLUCIÓN AL ERROR 500 AL EDITAR USUARIO: Verifica si el nombre ya está en uso
            usuario_existente = User.query.filter_by(username=nuevo_username).first()
            if usuario_existente and usuario_existente.id != user.id:
                flash('El nombre de usuario ya está en uso. Elige otro.', 'danger')
                return redirect(url_for('editar_usuario', id=user.id))

            user.username = nuevo_username
            user.role = request.form['role']
            
            # Solo actualiza la contraseña si el usuario escribió algo en el campo
            new_password = request.form.get('password')
            if new_password:
                user.password_hash = generate_password_hash(new_password)
                
            db.session.commit()
            flash('Usuario actualizado correctamente!', 'success')
            return redirect(url_for('usuarios'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar usuario: {str(e)}', 'danger')
            return redirect(url_for('editar_usuario', id=user.id))
            
    return render_template('editar_usuario.html', user=user, hostname=socket.gethostname())

@app.route('/usuario/eliminar/<int:id>')
@login_required
def eliminar_usuario(id):
    if session.get('role') not in ['admin', 'sistemas']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('usuarios'))

    # Evita que te borres a ti mismo
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
    app.run(host='0.0.0.0', port=5000, debug=False)
