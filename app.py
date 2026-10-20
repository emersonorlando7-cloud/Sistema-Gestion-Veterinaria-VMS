# Importación de librerías necesarias
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash # Para encriptar contraseñas
from functools import wraps # Para crear el decorador @login_required
import socket

app = Flask(__name__)
app.secret_key = 'clave_secreta_vetsystem_segura' # Necesario para manejar sesiones

# CONEXIÓN A HAPROXY (192.168.56.10) EN LUGAR DE DIRECTAMENTE A DB-01
# Esto permite que si db-01 cae, HAProxy enrute a db-02 automáticamente.
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.10:3306/vet_clinic_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# MODELOS (Tablas de la base de datos)
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False) # Guarda la contraseña encriptada
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
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id'))
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(50))
    breed = db.Column(db.String(50))
    age = db.Column(db.Integer)
    weight = db.Column(db.Numeric(5, 2))

class Consultation(db.Model):
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    pet_id = db.Column(db.Integer, db.ForeignKey('pets.id'))
    reason = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    consultation_date = db.Column(db.DateTime, server_default=db.func.now())

# DECORADOR DE SEGURIDAD
# Envuelve las rutas para verificar si hay una sesión activa antes de dejarte pasar.
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión primero.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# RUTA: LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        # check_password_hash compara la contraseña escrita con el hash guardado en BD
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            return redirect(url_for('inicio'))
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
    return render_template('login.html')

# RUTA: CERRAR SESIÓN
@app.route('/logout')
def logout():
    session.clear() # Borra todos los datos de la sesión
    return redirect(url_for('login'))

# RUTAS PROTEGIDAS
@app.route('/')
@login_required
def index():
    return redirect(url_for('inicio'))

@app.route('/inicio')
@login_required
def inicio():
    total_pacientes = Pet.query.count()
    total_duenos = Owner.query.count()
    hostname = socket.gethostname()
    return render_template('inicio.html', hostname=hostname, total_pacientes=total_pacientes, total_duenos=total_duenos)

@app.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar_paciente():
    if request.method == 'POST':
        try:
            owner = Owner(name=request.form['owner_name'], phone=request.form.get('owner_phone'))
            db.session.add(owner)
            db.session.flush()
            pet = Pet(owner_id=owner.id, name=request.form['pet_name'], species=request.form.get('pet_species'))
            db.session.add(pet)
            db.session.commit()
            flash('Paciente registrado!', 'success')
            return redirect(url_for('pacientes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    return render_template('index.html', hostname=socket.gethostname())

@app.route('/pacientes')
@login_required
def pacientes():
    lista = db.session.query(Pet, Owner).join(Owner, Pet.owner_id == Owner.id).all()
    return render_template('pacientes.html', pacientes=lista, hostname=socket.gethostname())

# RUTA: ELIMINAR PACIENTE (Solo Admin)
@app.route('/paciente/eliminar/<int:id>')
@login_required
def eliminar_paciente(id):
    # Verifica el rol antes de permitir la acción
    if session.get('role') != 'admin':
        flash('No tienes permiso para eliminar.', 'danger')
        return redirect(url_for('pacientes'))
    
    pet = Pet.query.get_or_404(id)
    owner = Owner.query.get(pet.owner_id)
    db.session.delete(pet)
    db.session.delete(owner)
    db.session.commit()
    flash('Paciente eliminado.', 'success')
    return redirect(url_for('pacientes'))

# RUTA: GESTIÓN DE USUARIOS (Solo Admin)
@app.route('/usuarios', methods=['GET', 'POST'])
@login_required
def usuarios():
    if session.get('role') != 'admin':
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        # Encripta la contraseña antes de guardarla
        hashed_pw = generate_password_hash(password)
        nuevo_user = User(username=username, password_hash=hashed_pw, role=role)
        db.session.add(nuevo_user)
        db.session.commit()
        flash('Usuario creado!', 'success')
    
    lista_users = User.query.all()
    return render_template('usuarios.html', usuarios=lista_users, hostname=socket.gethostname())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
