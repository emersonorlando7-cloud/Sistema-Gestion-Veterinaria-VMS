# ==============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================
# Flask: El framework para crear la aplicación web.
# render_template: Para cargar los archivos HTML.
# request: Para capturar los datos de los formularios.
# redirect/url_for: Para redirigir al usuario entre páginas.
# flash: Para mostrar mensajes de éxito o error (los cuadros de colores).
# session: Para manejar el inicio de sesión (login) del usuario.
from flask import Flask, render_template, request, redirect, url_for, flash, session

# SQLAlchemy: El ORM que nos permite interactuar con MySQL usando clases de Python.
from flask_sqlalchemy import SQLAlchemy

# generate_password_hash: Convierte una contraseña en un texto encriptado.
# check_password_hash: Compara la contraseña escrita con la encriptada en la BD.
from werkzeug.security import generate_password_hash, check_password_hash

# wraps: Se usa para crear el decorador @login_required (protege las rutas).
from functools import wraps

# socket: Para obtener el nombre de la máquina (app-01 o app-02).
import socket

# ==============================================================================
# 2. CONFIGURACIÓN INICIAL
# ==============================================================================
app = Flask(__name__)

# Clave secreta necesaria para firmar las cookies de sesión (Login).
app.secret_key = 'clave_secreta_vetsystem_segura'

# CONEXIÓN A LA BASE DE DATOS:
# Apunta a HAProxy (192.168.56.10) en el puerto 3306.
# Esto permite que, si db-01 se cae, HAProxy envíe el tráfico a db-02.
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.10:3306/vet_clinic_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- SOLUCIÓN AL ERROR 2013 (Pérdida de conexión) ---
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280      # Recicla conexiones viejas cada 280s
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 20       # Tiempo máximo de espera al conectar
app.config['SQLALCHEMY_POOL_PRE_PING'] = True    # Hace un "ping" antes de usar la conexión para verificar que siga viva

db = SQLAlchemy(app)

# ==============================================================================
# 3. MODELOS (Mapeo de las tablas de MySQL a clases de Python)
# ==============================================================================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    # unique=True evita que haya dos usuarios con el mismo nombre.
    username = db.Column(db.String(50), unique=True, nullable=False) 
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False) # admin, sistemas, veterinario, etc.

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
    # ForeignKey conecta a la mascota con un dueño específico.
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id')) 
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(50))
    breed = db.Column(db.String(50))
    age = db.Column(db.Integer)
    weight = db.Column(db.Numeric(5, 2))

class Consultation(db.Model):
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    # ForeignKey conecta la consulta médica con la mascota.
    pet_id = db.Column(db.Integer, db.ForeignKey('pets.id')) 
    reason = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    # server_default=db.func.now() guarda automáticamente la fecha y hora actual de MySQL.
    consultation_date = db.Column(db.DateTime, server_default=db.func.now())

# ==============================================================================
# 4. CREACIÓN AUTOMÁTICA DEL USUARIO ADMIN
# ==============================================================================
# Esto se ejecuta una sola vez al encender la aplicación.
with app.app_context():
    try:
        db.create_all() # Crea las tablas en MySQL si no existen
        # Busca si 'emerson_7' ya existe. Si no, lo crea.
        if not User.query.filter_by(username='emerson_7').first():
            admin_user = User(username='emerson_7', password_hash=generate_password_hash('P@ssw0rd'), role='admin')
            db.session.add(admin_user)
            db.session.commit()
    except Exception as e:
        print(f"Error al crear usuario inicial: {e}")

# ==============================================================================
# 5. DECORADOR DE SEGURIDAD
# ==============================================================================
# Esta función "envuelve" a las rutas para verificar que el usuario esté logueado.
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión primero.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==============================================================================
# 6. RUTAS DE LA APLICACIÓN
# ==============================================================================

# --- RUTA: LOGIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            user = User.query.filter_by(username=username).first()
            # Compara la contraseña en texto plano con el hash de la BD.
            if user and check_password_hash(user.password_hash, password):
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                return redirect(url_for('inicio'))
            else:
                flash('Usuario o contraseña incorrectos', 'danger')
        except Exception:
            # Si hay un micro-corte de red a la BD, muestra error pero no rompe la app.
            flash('Error de conexión a la base de datos.', 'danger')
    return render_template('login.html')

# --- RUTA: CERRAR SESIÓN ---
@app.route('/logout')
def logout():
    session.clear() # Borra los datos de la sesión
    return redirect(url_for('login'))

# --- RUTA: INICIO (Panel de Control) ---
@app.route('/')
@login_required
def index():
    return redirect(url_for('inicio'))

@app.route('/inicio')
@login_required
def inicio():
    try:
        # Cuenta los registros para mostrar el resumen en pantalla.
        total_pacientes = Pet.query.count()
        total_duenos = Owner.query.count()
        total_consultas = Consultation.query.count()
    except Exception:
        # Si la base falla, muestra 0 en lugar de romper la página.
        total_pacientes = 0
        total_duenos = 0
        total_consultas = 0
    return render_template('inicio.html', hostname=socket.gethostname(), total_pacientes=total_pacientes, total_duenos=total_duenos, total_consultas=total_consultas)

# --- RUTA: REGISTRAR PACIENTE ---
@app.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar_paciente():
    if request.method == 'POST':
        try:
            # 1. Guarda al Dueño y usa flush() para obtener su ID.
            owner = Owner(name=request.form['owner_name'], phone=request.form.get('owner_phone'), email=request.form.get('owner_email'), address=request.form.get('owner_address'))
            db.session.add(owner)
            db.session.flush() 
            
            # 2. Guarda la Mascota.
            age = request.form.get('pet_age')
            weight = request.form.get('pet_weight')
            
            # CONVERSIÓN SEGURA: Si la edad o el peso están vacíos, guarda "None" (nulo) para evitar errores.
            pet = Pet(owner_id=owner.id, name=request.form['pet_name'], species=request.form.get('pet_species'), breed=request.form.get('pet_breed'), age=int(age) if age else None, weight=float(weight) if weight else None)
            db.session.add(pet)
            
            # 3. Confirma todos los cambios en la base de datos.
            db.session.commit()
            flash('Paciente registrado exitosamente!', 'success')
            return redirect(url_for('pacientes'))
        except Exception as e:
            db.session.rollback() # Deshace cambios si hay error
            flash(f'Error al registrar: {str(e)}', 'danger')
    return render_template('index.html', hostname=socket.gethostname())

# --- RUTA: LISTA DE PACIENTES ---
@app.route('/pacientes')
@login_required
def pacientes():
    try:
        # JOIN: Une las tablas Pet y Owner para mostrar los datos juntos.
        lista = db.session.query(Pet, Owner).join(Owner, Pet.owner_id == Owner.id).all()
    except Exception:
        lista = []
    return render_template('pacientes.html', pacientes=lista, hostname=socket.gethostname())

# --- RUTA: VER DETALLES DE UN PACIENTE ---
@app.route('/paciente/ver/<int:id>')
@login_required
def ver_paciente(id):
    pet = Pet.query.get_or_404(id)
    owner = Owner.query.get(pet.owner_id)
    # Trae todas las consultas de la mascota, ordenadas de la más reciente a la más antigua.
    consultas = Consultation.query.filter_by(pet_id=pet.id).order_by(Consultation.consultation_date.desc()).all()
    return render_template('ver_paciente.html', pet=pet, owner=owner, consultas=consultas, hostname=socket.gethostname())

# --- RUTA: EDITAR PACIENTE ---
@app.route('/paciente/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_paciente(id):
    # BLINDAJE: Atrapa el error si la base de datos falla justo al intentar cargar los datos para editar.
    try:
        pet = Pet.query.get_or_404(id)
        owner = Owner.query.get(pet.owner_id)
    except Exception as e:
        flash('Error de conexión con la base de datos. Recargue la página e intente de nuevo.', 'danger')
        return redirect(url_for('pacientes'))

    if request.method == 'POST':
        try:
            owner.name = request.form['owner_name']
            owner.phone = request.form.get('owner_phone')
            owner.email = request.form.get('owner_email')
            owner.address = request.form.get('owner_address')
            
            pet.name = request.form['pet_name']
            pet.species = request.form.get('pet_species')
            pet.breed = request.form.get('pet_breed')
            
            # CONVERSIÓN SEGURA para evitar error 500 con campos vacíos.
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

# --- RUTA: ELIMINAR PACIENTE ---
@app.route('/paciente/eliminar/<int:id>')
@login_required
def eliminar_paciente(id):
    # Solo admin y sistemas pueden borrar.
    if session.get('role') not in ['admin', 'sistemas']:
        flash('No tienes permiso para eliminar.', 'danger')
        return redirect(url_for('pacientes'))
    try:
        pet = Pet.query.get_or_404(id)
        owner = Owner.query.get(pet.owner_id)
        
        # SOLUCIÓN AL ERROR 1451 (Llave foránea): 
        # Primero se borran las consultas, luego la mascota y por último el dueño.
        Consultation.query.filter_by(pet_id=pet.id).delete()
        db.session.flush() # Fuerza a MySQL a procesar el borrado de consultas AHORA.
        
        db.session.delete(pet)
        db.session.flush()
        db.session.delete(owner)
        
        db.session.commit()
        flash('Paciente eliminado.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'danger')
    return redirect(url_for('pacientes'))

# --- RUTA: GESTIÓN DE USUARIOS (Crear y Listar) ---
@app.route('/usuarios', methods=['GET', 'POST'])
@login_required
def usuarios():
    # Validación de roles.
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

# --- RUTA: EDITAR USUARIO ---
@app.route('/usuario/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    if session.get('role') not in ['admin', 'sistemas']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('usuarios'))

    # BLINDAJE: Atrapa el error si hay un micro-corte al buscar al usuario.
    try:
        user = User.query.get_or_404(id)
    except Exception as e:
        flash('Error de conexión con la base de datos. Recargue la página e intente de nuevo.', 'danger')
        return redirect(url_for('usuarios'))
    
    if request.method == 'POST':
        try:
            nuevo_username = request.form['username']
            
            # VALIDACIÓN: Si el nombre ya existe y es de otro usuario, lanza error.
            usuario_existente = User.query.filter_by(username=nuevo_username).first()
            if usuario_existente and usuario_existente.id != user.id:
                flash('El nombre de usuario ya está en uso. Elige otro.', 'danger')
                return redirect(url_for('editar_usuario', id=user.id))

            user.username = nuevo_username
            user.role = request.form['role']
            
            # Solo actualiza la contraseña si se escribió algo nuevo en el campo.
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

# --- RUTA: ELIMINAR USUARIO ---
@app.route('/usuario/eliminar/<int:id>')
@login_required
def eliminar_usuario(id):
    if session.get('role') not in ['admin', 'sistemas']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('usuarios'))

    # Protección: Evita que el usuario logueado se borre a sí mismo.
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

# ==============================================================================
# 7. ARRANQUE DEL SERVIDOR
# ==============================================================================
if __name__ == '__main__':
    # host='0.0.0.0' permite conexiones externas (necesario para HAProxy).
    # debug=False es obligatorio en producción para ocultar errores al usuario final.
    app.run(host='0.0.0.0', port=5000, debug=False)
