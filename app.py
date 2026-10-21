# ==============================================================================
# IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import socket

# ==============================================================================
# CONFIGURACIÓN INICIAL DE LA APLICACIÓN
# ==============================================================================
app = Flask(__name__)
# Clave secreta necesaria para firmar las cookies de sesión (login)
app.secret_key = 'clave_secreta_vetsystem_segura'

# URL de conexión a la base de datos a través de HAProxy (192.168.56.10)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.10:3306/vet_clinic_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- SOLUCIÓN AL ERROR 2013 (Lost connection) ---
# 1. POOL_RECYCLE: Si una conexión tiene más de 280 segundos inactiva, la cierra y abre una nueva.
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280
# 2. POOL_TIMEOUT: Tiempo máximo de espera para obtener una conexión.
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 20
# 3. PRE_PING: Antes de usar la conexión, hace un "ping" a MySQL para verificar que sigue viva.
#    Si está muerta, la reconecta automáticamente, evitando el error 500.
app.config['SQLALCHEMY_POOL_PRE_PING'] = True

# Inicializamos la base de datos
db = SQLAlchemy(app)

# ==============================================================================
# MODELOS DE LA BASE DE DATOS (Tablas)
# ==============================================================================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'admin' o 'vet'

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
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id')) # Relación con el dueño
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(50))
    breed = db.Column(db.String(50))
    age = db.Column(db.Integer)
    weight = db.Column(db.Numeric(5, 2))

class Consultation(db.Model):
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    pet_id = db.Column(db.Integer, db.ForeignKey('pets.id')) # Relación con la mascota
    reason = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    consultation_date = db.Column(db.DateTime, server_default=db.func.now())

# ==============================================================================
# CREACIÓN AUTOMÁTICA DEL USUARIO ADMINISTRADOR
# ==============================================================================
# Este bloque se ejecuta una sola vez al arrancar la app para crear el admin si no existe.
with app.app_context():
    try:
        db.create_all() # Crea las tablas si no existen
        if not User.query.filter_by(username='emerson_7').first():
            admin_user = User(
                username='emerson_7', 
                password_hash=generate_password_hash('P@ssw0rd'), # Encripta la contraseña
                role='admin'
            )
            db.session.add(admin_user)
            db.session.commit()
    except Exception as e:
        # Si falla la conexión a la BD al arrancar, imprime el error pero no tumba la app.
        print(f"Error al crear usuario inicial: {e}")

# ==============================================================================
# DECORADOR DE SEGURIDAD (Protege las rutas)
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
# RUTAS DE LA APLICACIÓN
# ==============================================================================

# --- RUTA: LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            # Busca al usuario en la BD
            user = User.query.filter_by(username=username).first()
            # Verifica que la contraseña coincida con el hash encriptado
            if user and check_password_hash(user.password_hash, password):
                # Guarda los datos en la sesión (cookies)
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                return redirect(url_for('inicio'))
            else:
                flash('Usuario o contraseña incorrectos', 'danger')
        except Exception as e:
            # Si hay un micro-corte de red, avisa al usuario sin romper la página.
            flash('Error de conexión a la base de datos. Intente de nuevo.', 'danger')
            print(f"Error en login: {e}")
            
    return render_template('login.html')

# --- RUTA: CERRAR SESIÓN ---
@app.route('/logout')
def logout():
    session.clear() # Borra la sesión
    return redirect(url_for('login'))

# --- RUTA: REDIRECCIÓN INICIAL ---
@app.route('/')
@login_required
def index():
    return redirect(url_for('inicio'))

# --- RUTA: PANEL DE CONTROL ---
@app.route('/inicio')
@login_required
def inicio():
    try:
        # Cuenta los registros en la BD
        total_pacientes = Pet.query.count()
        total_duenos = Owner.query.count()
    except Exception as e:
        # Si falla la BD, muestra un aviso y envía valores por defecto en 0.
        flash('Error al cargar datos. Recargue la página.', 'warning')
        total_pacientes = 0
        total_duenos = 0
        
    hostname = socket.gethostname() # Obtiene el nombre del servidor (app-01 o app-02)
    return render_template('inicio.html', hostname=hostname, total_pacientes=total_pacientes, total_duenos=total_duenos)

# --- RUTA: REGISTRAR PACIENTE ---
@app.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar_paciente():
    if request.method == 'POST':
        try:
            # 1. Guarda al Dueño
            owner = Owner(name=request.form['owner_name'], phone=request.form.get('owner_phone'))
            db.session.add(owner)
            db.session.flush() # Obtiene el ID del dueño recién creado
            
            # 2. Guarda a la Mascota vinculada al dueño
            pet = Pet(owner_id=owner.id, name=request.form['pet_name'], species=request.form.get('pet_species'))
            db.session.add(pet)
            
            # 3. Confirma y guarda definitivamente en MySQL
            db.session.commit()
            flash('Paciente registrado exitosamente!', 'success')
            return redirect(url_for('pacientes'))
        except Exception as e:
            # Si falla algo, deshace el cambio para no dejar datos basura y muestra error.
            db.session.rollback()
            flash(f'Error al registrar: {str(e)}', 'danger')
    return render_template('index.html', hostname=socket.gethostname())

# --- RUTA: VER LISTA DE PACIENTES ---
@app.route('/pacientes')
@login_required
def pacientes():
    try:
        # Consulta (JOIN) para traer mascotas con sus dueños
        lista = db.session.query(Pet, Owner).join(Owner, Pet.owner_id == Owner.id).all()
    except Exception as e:
        flash('Error al cargar la lista de pacientes.', 'warning')
        lista = [] # Envía una lista vacía si hay error de BD
        
    return render_template('pacientes.html', pacientes=lista, hostname=socket.gethostname())

# --- RUTA: ELIMINAR PACIENTE (Solo Admin) ---
@app.route('/paciente/eliminar/<int:id>')
@login_required
def eliminar_paciente(id):
    # Verifica el rol antes de dejar borrar
    if session.get('role') != 'admin':
        flash('No tienes permiso para eliminar.', 'danger')
        return redirect(url_for('pacientes'))
    try:
        # Busca la mascota y su dueño, y los borra
        pet = Pet.query.get_or_404(id)
        owner = Owner.query.get(pet.owner_id)
        db.session.delete(pet)
        db.session.delete(owner)
        db.session.commit()
        flash('Paciente eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error al eliminar el paciente.', 'danger')
    return redirect(url_for('pacientes'))

# --- RUTA: GESTIÓN DE USUARIOS (Solo Admin) ---
@app.route('/usuarios', methods=['GET', 'POST'])
@login_required
def usuarios():
    if session.get('role') != 'admin':
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        try:
            # Crea un nuevo usuario encriptando su contraseña
            username = request.form['username']
            password = request.form['password']
            role = request.form['role']
            hashed_pw = generate_password_hash(password)
            nuevo_user = User(username=username, password_hash=hashed_pw, role=role)
            db.session.add(nuevo_user)
            db.session.commit()
            flash('Usuario creado exitosamente!', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error al crear el usuario.', 'danger')
    
    try:
        # Trae la lista de todos los usuarios para mostrarla
        lista_users = User.query.all()
    except Exception:
        lista_users = []
        
    return render_template('usuarios.html', usuarios=lista_users, hostname=socket.gethostname())

# ==============================================================================
# EJECUCIÓN DE LA APLICACIÓN
# ==============================================================================
if __name__ == '__main__':
    # host='0.0.0.0' permite conexiones externas (HAProxy).
    # debug=False en producción evita mostrar errores técnicos al usuario final y mejora el rendimiento.
    app.run(host='0.0.0.0', port=5000, debug=False)
