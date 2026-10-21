# ==============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================
# Flask: El framework web para manejar las rutas y peticiones.
# SQLAlchemy: La herramienta para conectarse y manipular la base de datos MySQL.
# generate_password_hash/check_password_hash: Para encriptar y verificar contraseñas.
# wraps: Para crear el decorador de seguridad (login_required).
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import socket # Para obtener el nombre del servidor (app-01 o app-02)

# ==============================================================================
# 2. CONFIGURACIÓN INICIAL
# ==============================================================================
app = Flask(__name__)
app.secret_key = 'clave_secreta_vetsystem_segura' # Necesario para usar 'session'

# Conexión a la base de datos a través de HAProxy (192.168.56.10)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.10:3306/vet_clinic_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- SOLUCIÓN AL ERROR 2013 (Pérdida de conexión) ---
# Recicla las conexiones cada 280 segundos para que MySQL no las cierre por inactividad.
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280
# Tiempo máximo de espera para obtener una conexión.
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 20
# Hace un "ping" a la base de datos antes de usarla. Si está caída, se reconecta sola.
app.config['SQLALCHEMY_POOL_PRE_PING'] = True

db = SQLAlchemy(app)

# ==============================================================================
# 3. MODELOS (Tablas de la Base de Datos)
# ==============================================================================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False) # Contraseña encriptada
    role = db.Column(db.String(50), nullable=False) # admin, sistemas, vet, etc.

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
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id')) # Conecta con el dueño
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(50))
    breed = db.Column(db.String(50))
    age = db.Column(db.Integer)
    weight = db.Column(db.Numeric(5, 2))

class Consultation(db.Model):
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    pet_id = db.Column(db.Integer, db.ForeignKey('pets.id')) # Conecta con la mascota
    reason = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    consultation_date = db.Column(db.DateTime, server_default=db.func.now())

# ==============================================================================
# 4. CREACIÓN AUTOMÁTICA DEL ADMINISTRADOR
# ==============================================================================
# Al arrancar la app, verifica si existe el usuario emerson_7. Si no, lo crea.
with app.app_context():
    try:
        db.create_all() # Crea las tablas si no existen
        if not User.query.filter_by(username='emerson_7').first():
            admin_user = User(username='emerson_7', password_hash=generate_password_hash('P@ssw0rd'), role='admin')
            db.session.add(admin_user)
            db.session.commit()
    except Exception as e:
        print(f"Error al crear usuario inicial: {e}")

# ==============================================================================
# 5. DECORADOR DE SEGURIDAD
# ==============================================================================
# Protege las rutas. Si no hay sesión, redirige al login.
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            # Busca al usuario y compara la contraseña encriptada
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password_hash, password):
                # Guarda los datos en la sesión si es correcto
                session['user_id'] = user.id
                session['username'] = user.username
                session['role'] = user.role
                return redirect(url_for('inicio'))
            else:
                flash('Usuario o contraseña incorrectos', 'danger')
        except Exception:
            flash('Error de conexión. Intente de nuevo.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear() # Borra los datos de la sesión
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('inicio'))

@app.route('/inicio')
@login_required
def inicio():
    try:
        # Cuenta los registros para mostrar en el panel
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
            # 1. Guarda al Dueño
            owner = Owner(name=request.form['owner_name'], phone=request.form.get('owner_phone'))
            db.session.add(owner)
            db.session.flush() # Obtiene el ID del dueño
            
            # 2. Guarda la Mascota asignándole el ID del dueño
            pet = Pet(owner_id=owner.id, name=request.form['pet_name'], species=request.form.get('pet_species'))
            db.session.add(pet)
            db.session.commit()
            flash('Paciente registrado exitosamente!', 'success')
            return redirect(url_for('pacientes'))
        except Exception as e:
            db.session.rollback() # Deshace cambios si hay error
            flash(f'Error al registrar: {str(e)}', 'danger')
    return render_template('index.html', hostname=socket.gethostname())

@app.route('/pacientes')
@login_required
def pacientes():
    try:
        # Une la tabla de mascotas con la de dueños para mostrar todo junto
        lista = db.session.query(Pet, Owner).join(Owner, Pet.owner_id == Owner.id).all()
    except Exception:
        lista = []
    return render_template('pacientes.html', pacientes=lista, hostname=socket.gethostname())

@app.route('/paciente/eliminar/<int:id>')
@login_required
def eliminar_paciente(id):
    # Verifica si el rol está permitido para eliminar (admin o sistemas)
    if session.get('role') not in ['admin', 'sistemas']:
        flash('No tienes permiso para eliminar.', 'danger')
        return redirect(url_for('pacientes'))
    
    try:
        pet = Pet.query.get_or_404(id)
        owner = Owner.query.get(pet.owner_id)
        
        # --- SOLUCIÓN AL ERROR DE LLAVE FORÁNEA ---
        # Borra primero las consultas asociadas a esa mascota.
        # Así MySQL no bloquea el borrado por tener registros dependientes.
        Consultation.query.filter_by(pet_id=pet.id).delete()
        
        # Ahora sí, borra la mascota y al dueño
        db.session.delete(pet)
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
    # Solo admin o sistemas pueden gestionar usuarios
    if session.get('role') not in ['admin', 'sistemas']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        try:
            # Crea un nuevo usuario con contraseña encriptada
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

# ==============================================================================
# 7. ARRANQUE DEL SERVIDOR
# ==============================================================================
if __name__ == '__main__':
    # host='0.0.0.0' permite conexiones externas. debug=False para producción.
    app.run(host='0.0.0.0', port=5000, debug=False)
