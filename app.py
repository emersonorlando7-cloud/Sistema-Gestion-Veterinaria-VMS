from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import socket
import time
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'clave_secreta_vetsystem_segura'

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.10:3306/vet_clinic_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- CONFIGURACIÓN DEL POOL DE CONEXIONES (SOLUCIÓN A LA LENTITUD) ---
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'max_overflow': 20,
    'pool_recycle': 280,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

# --- LIMPIEZA AUTOMÁTICA DE SESIÓN (EVITA CONEXIONES ZOMBIS) ---
@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    permissions = db.Column(db.Text, nullable=False)

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
    appointment_date = db.Column(db.DateTime, nullable=False)

with app.app_context():
    try:
        db.create_all()
        if not User.query.filter_by(username='emerson_7').first():
            admin_user = User(username='emerson_7', password_hash=generate_password_hash('P@ssw0rd'), role='admin')
            db.session.add(admin_user)
            db.session.commit()
    except Exception as e:
        print(f"Error al crear usuario inicial: {e}")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión primero.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            user_role = session.get('role')
            if user_role in ['admin', 'sistemas']:
                return f(*args, **kwargs)
            role_db = Role.query.filter_by(name=user_role).first()
            if role_db and (permission in role_db.permissions.split(',') or 'all' in role_db.permissions.split(',')):
                return f(*args, **kwargs)
            return """
            <script>
                alert('⛔ No tienes permisos para acceder a esta sección.');
                window.history.back();
            </script>
            """
        return decorated_function
    return decorator

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
        total_consultas = Consultation.query.count()
        hoy = date.today()
        consultas_hoy = Consultation.query.filter(db.func.date(Consultation.appointment_date) == hoy).count()
        citas_hoy = db.session.query(Consultation, Pet, Owner).join(Pet, Consultation.pet_id == Pet.id).join(Owner, Pet.owner_id == Owner.id).filter(db.func.date(Consultation.appointment_date) == hoy).order_by(Consultation.appointment_date).all()
    except Exception:
        total_pacientes = 0
        total_duenos = 0
        total_consultas = 0
        consultas_hoy = 0
        citas_hoy = []
    return render_template('inicio.html', hostname=socket.gethostname(), total_pacientes=total_pacientes, total_duenos=total_duenos, total_consultas=total_consultas, consultas_hoy=consultas_hoy, citas_hoy=citas_hoy)

@app.route('/registrar', methods=['GET', 'POST'])
@login_required
@permission_required('crear_pacientes')
def registrar_paciente():
    if request.method == 'POST':
        intentos = 3
        for intento in range(intentos):
            try:
                owner = Owner(name=request.form['owner_name'], phone=request.form.get('owner_phone'), email=request.form.get('owner_email'), address=request.form.get('owner_address'))
                db.session.add(owner)
                db.session.flush()
                
                age = request.form.get('pet_age')
                weight = request.form.get('pet_weight')
                pet = Pet(owner_id=owner.id, name=request.form['pet_name'], species=request.form.get('pet_species'), breed=request.form.get('pet_breed'), age=int(age) if age else None, weight=float(weight) if weight else None)
                db.session.add(pet)
                db.session.flush()
                
                appointment_str = request.form.get('appointment_date')
                if appointment_str:
                    appointment_dt = datetime.strptime(appointment_str, '%Y-%m-%dT%H:%M')
                else:
                    appointment_dt = datetime.now()

                cita_existente = Consultation.query.filter_by(appointment_date=appointment_dt).first()
                if cita_existente:
                    flash('Error: Este horario ya está ocupado. Por favor elige otro.', 'warning')
                    db.session.rollback()
                    return redirect(url_for('registrar_paciente'))

                consultation = Consultation(pet_id=pet.id, reason=request.form.get('reason'), diagnosis=request.form.get('diagnosis'), appointment_date=appointment_dt)
                db.session.add(consultation)
                db.session.commit()
                
                flash('Paciente y cita registrados exitosamente!', 'success')
                return redirect(url_for('pacientes'))
            except Exception as e:
                db.session.rollback()
                if intento < (intentos - 1):
                    time.sleep(1)
                else:
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

@app.route('/paciente/ver/<int:id>')
@login_required
def ver_paciente(id):
    try:
        pet = Pet.query.get_or_404(id)
        owner = Owner.query.get(pet.owner_id)
        consultas = Consultation.query.filter_by(pet_id=pet.id).order_by(Consultation.appointment_date.desc()).all()
    except Exception:
        db.session.rollback()
        flash('Error de conexión. Recargue la página e intente de nuevo.', 'danger')
        return redirect(url_for('pacientes'))
        
    return render_template('ver_paciente.html', pet=pet, owner=owner, consultas=consultas, hostname=socket.gethostname())

@app.route('/paciente/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('editar_pacientes')
def editar_paciente(id):
    try:
        pet = Pet.query.get_or_404(id)
        owner = Owner.query.get(pet.owner_id)
    except Exception:
        flash('Error de conexión con la base de datos. Recargue la página.', 'danger')
        return redirect(url_for('pacientes'))

    if request.method == 'POST':
        intentos = 3
        for intento in range(intentos):
            try:
                owner.name = request.form['owner_name']
                owner.phone = request.form.get('owner_phone')
                owner.email = request.form.get('owner_email')
                owner.address = request.form.get('owner_address')
                pet.name = request.form['pet_name']
                pet.species = request.form.get('pet_species')
                pet.breed = request.form.get('pet_breed')
                age = request.form.get('pet_age')
                weight = request.form.get('pet_weight')
                pet.age = int(age) if age else None
                pet.weight = float(weight) if weight else None
                db.session.commit()
                flash('Paciente actualizado correctamente!', 'success')
                return redirect(url_for('pacientes'))
            except Exception as e:
                db.session.rollback()
                if intento < (intentos - 1):
                    time.sleep(1)
                else:
                    flash(f'Error al actualizar paciente: {str(e)}', 'danger')
    return render_template('editar_paciente.html', pet=pet, owner=owner, hostname=socket.gethostname())

@app.route('/paciente/eliminar/<int:id>')
@login_required
@permission_required('eliminar_pacientes')
def eliminar_paciente(id):
    intentos = 3
    for intento in range(intentos):
        try:
            pet = Pet.query.get_or_404(id)
            owner = Owner.query.get(pet.owner_id)
            Consultation.query.filter_by(pet_id=pet.id).delete()
            db.session.flush()
            db.session.delete(pet)
            db.session.flush()
            db.session.delete(owner)
            db.session.commit()
            flash('Paciente eliminado.', 'success')
            return redirect(url_for('pacientes'))
        except Exception as e:
            db.session.rollback()
            if intento < (intentos - 1):
                time.sleep(1)
            else:
                flash(f'Error al eliminar: {str(e)}', 'danger')
    return redirect(url_for('pacientes'))

@app.route('/usuarios', methods=['GET', 'POST'])
@login_required
@permission_required('gestionar_usuarios')
def usuarios():
    if request.method == 'POST':
        intentos = 3
        for intento in range(intentos):
            try:
                username = request.form['username']
                password = request.form['password']
                role = request.form['role']
                hashed_pw = generate_password_hash(password)
                nuevo_user = User(username=username, password_hash=hashed_pw, role=role)
                db.session.add(nuevo_user)
                db.session.commit()
                flash('Usuario creado exitosamente!', 'success')
                break
            except Exception:
                db.session.rollback()
                if intento < (intentos - 1):
                    time.sleep(1)
                else:
                    flash('Error al crear el usuario.', 'danger')
    try:
        lista_users = User.query.all()
        lista_roles = Role.query.all()
    except Exception:
        lista_users = []
        lista_roles = []
    return render_template('usuarios.html', usuarios=lista_users, roles=lista_roles, hostname=socket.gethostname())

@app.route('/usuario/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('gestionar_usuarios')
def editar_usuario(id):
    try:
        user = User.query.get_or_404(id)
        lista_roles = Role.query.all()
    except Exception:
        flash('Error de conexión con la base de datos.', 'danger')
        return redirect(url_for('usuarios'))
    if request.method == 'POST':
        intentos = 3
        for intento in range(intentos):
            try:
                nuevo_username = request.form['username']
                usuario_existente = User.query.filter_by(username=nuevo_username).first()
                if usuario_existente and usuario_existente.id != user.id:
                    flash('El nombre de usuario ya está en uso.', 'danger')
                    return redirect(url_for('editar_usuario', id=user.id))
                user.username = nuevo_username
                user.role = request.form['role']
                new_password = request.form.get('password')
                if new_password:
                    user.password_hash = generate_password_hash(new_password)
                db.session.commit()
                flash('Usuario actualizado correctamente!', 'success')
                return redirect(url_for('usuarios'))
            except Exception as e:
                db.session.rollback()
                if intento < (intentos - 1):
                    time.sleep(1)
                else:
                    flash(f'Error al actualizar usuario: {str(e)}', 'danger')
    return render_template('editar_usuario.html', user=user, roles=lista_roles, hostname=socket.gethostname())

@app.route('/usuario/eliminar/<int:id>')
@login_required
@permission_required('gestionar_usuarios')
def eliminar_usuario(id):
    if id == session.get('user_id'):
        flash('No puedes eliminar tu propio usuario activo.', 'warning')
        return redirect(url_for('usuarios'))
    intentos = 3
    for intento in range(intentos):
        try:
            user = User.query.get_or_404(id)
            db.session.delete(user)
            db.session.commit()
            flash('Usuario eliminado correctamente.', 'success')
            return redirect(url_for('usuarios'))
        except Exception as e:
            db.session.rollback()
            if intento < (intentos - 1):
                time.sleep(1)
            else:
                flash(f'Error al eliminar el usuario: {str(e)}', 'danger')
    return redirect(url_for('usuarios'))

@app.route('/roles', methods=['GET', 'POST'])
@login_required
@permission_required('gestionar_usuarios')
def roles():
    if request.method == 'POST':
        try:
            name = request.form['role_name']
            permissions = request.form.getlist('permissions')
            perms_str = ','.join(permissions) if permissions else 'ninguno'
            nuevo_role = Role(name=name, permissions=perms_str)
            db.session.add(nuevo_role)
            db.session.commit()
            flash('Rol creado exitosamente!', 'success')
            return redirect(url_for('roles'))
        except Exception:
            db.session.rollback()
            flash('Error al crear el rol (quizás ya existe).', 'danger')
    lista_roles = Role.query.all()
    return render_template('roles.html', roles=lista_roles, hostname=socket.gethostname())

@app.route('/rol/eliminar/<int:id>')
@login_required
@permission_required('gestionar_usuarios')
def eliminar_rol(id):
    try:
        rol = Role.query.get_or_404(id)
        if rol.name in ['admin', 'sistemas']:
            flash('No puedes eliminar los roles base del sistema.', 'warning')
            return redirect(url_for('roles'))
        db.session.delete(rol)
        db.session.commit()
        flash('Rol eliminado correctamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el rol: {str(e)}', 'danger')
    return redirect(url_for('roles'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
