# ==============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================
# Flask: El framework para crear la aplicación web.
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

# time: Proporciona funciones relacionadas con el tiempo, como pausas en la ejecución.
import time 

# ==============================================================================
# 2. CONFIGURACIÓN INICIAL
# ==============================================================================
app = Flask(__name__)

# Clave secreta necesaria para firmar las cookies de sesión (Login).
app.secret_key = 'clave_secreta_vetsystem_segura' 

# CONEXIÓN A LA BASE DE DATOS: Apunta a HAProxy (192.168.56.10).
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.10:3306/vet_clinic_db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Desactiva el rastreo de modificaciones para ahorrar memoria.

# --- SOLUCIÓN AL ERROR 2013 (Pérdida de conexión) ---
app.config['SQLALCHEMY_POOL_RECYCLE'] = 280 # Recicla conexiones inactivas cada 280 segundos.
app.config['SQLALCHEMY_POOL_TIMEOUT'] = 20 # Tiempo máximo de espera (en segundos) al conectar.
app.config['SQLALCHEMY_POOL_PRE_PING'] = True # Hace un "ping" antes de usar la conexión para verificar que siga viva.

db = SQLAlchemy(app) # Inicializa la base de datos con la configuración de la app.

# ==============================================================================
# 3. MODELOS (Mapeo de las tablas de MySQL a clases de Python)
# ==============================================================================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True) # Llave primaria autoincremental.
    username = db.Column(db.String(50), unique=True, nullable=False) # El nombre debe ser único y no puede estar vacío.
    password_hash = db.Column(db.String(255), nullable=False) # Guarda la contraseña encriptada, no texto plano.
    role = db.Column(db.String(50), nullable=False) # Define los permisos (admin, sistemas, veterinario, etc.).

class Owner(db.Model):
    __tablename__ = 'owners'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False) # El nombre del dueño es obligatorio.
    phone = db.Column(db.String(20)) # El teléfono puede ser nulo.
    email = db.Column(db.String(100))
    address = db.Column(db.String(255))

class Pet(db.Model):
    __tablename__ = 'pets'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id')) # Llave foránea que conecta con la tabla owners.
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(50))
    breed = db.Column(db.String(50))
    age = db.Column(db.Integer)
    weight = db.Column(db.Numeric(5, 2))

class Consultation(db.Model):
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    pet_id = db.Column(db.Integer, db.ForeignKey('pets.id')) # Llave foránea que conecta con la tabla pets.
    reason = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    consultation_date = db.Column(db.DateTime, server_default=db.func.now()) # Asigna automáticamente la fecha y hora actual.

# ==============================================================================
# 4. CREACIÓN AUTOMÁTICA DEL USUARIO ADMIN
# ==============================================================================
with app.app_context(): # Contexto necesario para interactuar con la base de datos al iniciar.
    try:
        db.create_all() # Crea todas las tablas definidas en los modelos si no existen.
        if not User.query.filter_by(username='emerson_7').first(): # Verifica si el usuario admin ya existe.
            admin_user = User(username='emerson_7', password_hash=generate_password_hash('P@ssw0rd'), role='admin') # Crea el usuario con contraseña encriptada.
            db.session.add(admin_user) # Lo añade a la sesión de la base de datos.
            db.session.commit() # Guarda los cambios definitivamente.
    except Exception as e:
        print(f"Error al crear usuario inicial: {e}") # Imprime el error en consola si falla.

# ==============================================================================
# 5. DECORADOR DE SEGURIDAD
# ==============================================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: # Verifica si no hay un usuario logueado en la sesión actual.
            flash('Por favor, inicia sesión primero.', 'warning') # Muestra alerta de advertencia.
            return redirect(url_for('login')) # Lo redirige a la página de login.
        return f(*args, **kwargs) # Si está logueado, ejecuta la función original.
    return decorated_function

# ==============================================================================
# 6. RUTAS DE LA APLICACIÓN
# ==============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST': # Si el usuario envió el formulario...
        username = request.form['username']
        password = request.form['password']
        try:
            user = User.query.filter_by(username=username).first() # Busca al usuario en la BD.
            if user and check_password_hash(user.password_hash, password): # Compara la contraseña encriptada.
                session['user_id'] = user.id # Guarda el ID en la sesión (inicia sesión).
                session['username'] = user.username # Guarda el nombre de usuario.
                session['role'] = user.role # Guarda el rol del usuario.
                return redirect(url_for('inicio')) # Redirige al panel de control.
            else:
                flash('Usuario o contraseña incorrectos', 'danger') # Muestra error si no coincide.
        except Exception:
            flash('Error de conexión a la base de datos.', 'danger') # Captura si la base está caída.
    return render_template('login.html') # Carga el HTML del login si es GET.

@app.route('/logout')
def logout():
    session.clear() # Borra todos los datos de la sesión (cierra sesión).
    return redirect(url_for('login')) # Redirige al login.

@app.route('/')
@login_required # Protege la ruta: requiere estar logueado.
def index():
    return redirect(url_for('inicio'))

@app.route('/inicio')
@login_required
def inicio():
    try:
        total_pacientes = Pet.query.count() # Cuenta cuántas mascotas hay en total.
        total_duenos = Owner.query.count() # Cuenta cuántos dueños hay en total.
        total_consultas = Consultation.query.count() # Cuenta cuántas consultas hay en total.
    except Exception:
        total_pacientes = 0 # Si hay error de conexión, muestra 0 por defecto.
        total_duenos = 0
        total_consultas = 0
    return render_template('inicio.html', hostname=socket.gethostname(), total_pacientes=total_pacientes, total_duenos=total_duenos, total_consultas=total_consultas) # Envía los datos al HTML.

@app.route('/registrar', methods=['GET', 'POST'])
@login_required
def registrar_paciente():
    if request.method == 'POST':
        intentos = 3 # Define el número máximo de intentos de conexión.
        for intento in range(intentos): # Bucle que se repetirá hasta 3 veces si falla.
            try:
                owner = Owner(name=request.form['owner_name'], phone=request.form.get('owner_phone'), email=request.form.get('owner_email'), address=request.form.get('owner_address')) # Crea el dueño.
                db.session.add(owner) # Añade el dueño a la sesión.
                db.session.flush() # Fuerza a la BD a guardar el dueño para obtener su ID.
                
                age = request.form.get('pet_age')
                weight = request.form.get('pet_weight')
                
                pet = Pet(owner_id=owner.id, name=request.form['pet_name'], species=request.form.get('pet_species'), breed=request.form.get('pet_breed'), age=int(age) if age else None, weight=float(weight) if weight else None) # Crea la mascota y convierte edad/peso a números o nulos.
                db.session.add(pet) # Añade la mascota a la sesión.
                
                db.session.commit() # Guarda todos los cambios en la base de datos.
                flash('Paciente registrado exitosamente!', 'success') # Muestra mensaje de éxito.
                return redirect(url_for('pacientes')) # Redirige a la lista de pacientes.
            except Exception as e:
                db.session.rollback() # Cancela cualquier cambio pendiente si hay error.
                if intento < (intentos - 1): # Si no es el último intento...
                    time.sleep(1) # Espera 1 segundo para que HAProxy cambie de base de datos.
                else:
                    flash(f'Error al registrar (se reintentó {intentos} veces): {str(e)}', 'danger') # Muestra el error final.
    return render_template('index.html', hostname=socket.gethostname())

@app.route('/pacientes')
@login_required
def pacientes():
    try:
        lista = db.session.query(Pet, Owner).join(Owner, Pet.owner_id == Owner.id).all() # Consulta que une mascotas con sus dueños.
    except Exception:
        lista = [] # Si falla, envía una lista vacía.
    return render_template('pacientes.html', pacientes=lista, hostname=socket.gethostname())

@app.route('/paciente/ver/<int:id>')
@login_required
def ver_paciente(id):
    pet = Pet.query.get_or_404(id) # Busca la mascota por ID o lanza error 404 si no existe.
    owner = Owner.query.get(pet.owner_id) # Busca al dueño de la mascota.
    consultas = Consultation.query.filter_by(pet_id=pet.id).order_by(Consultation.consultation_date.desc()).all() # Trae el historial de consultas ordenado por fecha.
    return render_template('ver_paciente.html', pet=pet, owner=owner, consultas=consultas, hostname=socket.gethostname())

@app.route('/paciente/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_paciente(id):
    try:
        pet = Pet.query.get_or_404(id) # Busca la mascota a editar.
        owner = Owner.query.get(pet.owner_id) # Busca a su dueño.
    except Exception:
        flash('Error de conexión con la base de datos. Recargue la página e intente de nuevo.', 'danger') # Blinda la carga inicial.
        return redirect(url_for('pacientes'))

    if request.method == 'POST':
        intentos = 3 # Configuración de reintentos.
        for intento in range(intentos):
            try:
                owner.name = request.form['owner_name'] # Actualiza el nombre del dueño.
                owner.phone = request.form.get('owner_phone') # Actualiza el teléfono.
                owner.email = request.form.get('owner_email') # Actualiza el email.
                owner.address = request.form.get('owner_address') # Actualiza la dirección.
                
                pet.name = request.form['pet_name'] # Actualiza el nombre de la mascota.
                pet.species = request.form.get('pet_species') # Actualiza la especie.
                pet.breed = request.form.get('pet_breed') # Actualiza la raza.
                
                age = request.form.get('pet_age')
                weight = request.form.get('pet_weight')
                pet.age = int(age) if age else None # Convierte a entero o guarda nulo.
                pet.weight = float(weight) if weight else None # Convierte a decimal o guarda nulo.
                
                db.session.commit() # Guarda los cambios en la BD.
                flash('Paciente actualizado correctamente!', 'success') # Notifica al usuario.
                return redirect(url_for('pacientes')) # Redirige a la lista.
            except Exception as e:
                db.session.rollback() # Deshace los cambios en caso de error.
                if intento < (intentos - 1):
                    time.sleep(1) # Pausa de 1 segundo para reintentar.
                else:
                    flash(f'Error al actualizar paciente: {str(e)}', 'danger') # Notifica el error final.
            
    return render_template('editar_paciente.html', pet=pet, owner=owner, hostname=socket.gethostname())

@app.route('/paciente/eliminar/<int:id>')
@login_required
def eliminar_paciente(id):
    if session.get('role') not in ['admin', 'sistemas']: # Verifica que el usuario tenga permisos de administrador.
        flash('No tienes permiso para eliminar.', 'danger')
        return redirect(url_for('pacientes'))
    
    intentos = 3 # Configuración de reintentos.
    for intento in range(intentos):
        try:
            pet = Pet.query.get_or_404(id) # Busca la mascota.
            owner = Owner.query.get(pet.owner_id) # Busca al dueño.
            
            Consultation.query.filter_by(pet_id=pet.id).delete() # Borra primero las consultas (hijos).
            db.session.flush() # Fuerza el borrado en la BD inmediatamente.
            
            db.session.delete(pet) # Borra la mascota (padre).
            db.session.flush() # Fuerza el borrado.
            db.session.delete(owner) # Finalmente borra al dueño.
            
            db.session.commit() # Confirma todos los borrados.
            flash('Paciente eliminado.', 'success') # Notifica el éxito.
            return redirect(url_for('pacientes'))
        except Exception as e:
            db.session.rollback() # Deshace si hay algún error.
            if intento < (intentos - 1):
                time.sleep(1) # Espera 1 segundo antes de reintentar.
            else:
                flash(f'Error al eliminar: {str(e)}', 'danger')
    return redirect(url_for('pacientes'))

@app.route('/usuarios', methods=['GET', 'POST'])
@login_required
def usuarios():
    if session.get('role') not in ['admin', 'sistemas']: # Control de acceso por rol.
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        intentos = 3 # Configuración de reintentos.
        for intento in range(intentos):
            try:
                username = request.form['username'] # Captura el nuevo usuario.
                password = request.form['password'] # Captura la contraseña.
                role = request.form['role'] # Captura el rol.
                hashed_pw = generate_password_hash(password) # Encripta la contraseña.
                nuevo_user = User(username=username, password_hash=hashed_pw, role=role) # Crea el objeto.
                db.session.add(nuevo_user) # Lo añade a la sesión.
                db.session.commit() # Guarda en la BD.
                flash('Usuario creado exitosamente!', 'success')
                break # Sale del bucle si tuvo éxito.
            except Exception:
                db.session.rollback() # Deshace si falla.
                if intento < (intentos - 1):
                    time.sleep(1) # Reintenta tras 1 segundo.
                else:
                    flash('Error al crear el usuario (quizás ya existe o falló la red).', 'danger')
    
    try:
        lista_users = User.query.all() # Obtiene todos los usuarios para la tabla.
    except Exception:
        lista_users = [] # Lista vacía si falla la BD.
    return render_template('usuarios.html', usuarios=lista_users, hostname=socket.gethostname())

@app.route('/usuario/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    if session.get('role') not in ['admin', 'sistemas']: # Control de acceso.
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('usuarios'))

    try:
        user = User.query.get_or_404(id) # Busca el usuario a editar.
    except Exception:
        flash('Error de conexión con la base de datos. Recargue la página e intente de nuevo.', 'danger') # Blinda la carga.
        return redirect(url_for('usuarios'))
    
    if request.method == 'POST':
        intentos = 3 # Configuración de reintentos.
        for intento in range(intentos):
            try:
                nuevo_username = request.form['username'] # Nuevo nombre.
                
                usuario_existente = User.query.filter_by(username=nuevo_username).first() # Verifica si el nombre ya está tomado.
                if usuario_existente and usuario_existente.id != user.id: # Si existe y no es el mismo usuario...
                    flash('El nombre de usuario ya está en uso. Elige otro.', 'danger')
                    return redirect(url_for('editar_usuario', id=user.id))

                user.username = nuevo_username # Asigna el nuevo nombre.
                user.role = request.form['role'] # Asigna el nuevo rol.
                
                new_password = request.form.get('password') # Captura si se escribió nueva contraseña.
                if new_password: # Si se escribió...
                    user.password_hash = generate_password_hash(new_password) # La actualiza encriptada.
                    
                db.session.commit() # Guarda los cambios.
                flash('Usuario actualizado correctamente!', 'success')
                return redirect(url_for('usuarios'))
            except Exception as e:
                db.session.rollback()
                if intento < (intentos - 1):
                    time.sleep(1) # Pausa de reintento.
                else:
                    flash(f'Error al actualizar usuario: {str(e)}', 'danger')
            
    return render_template('editar_usuario.html', user=user, hostname=socket.gethostname())

@app.route('/usuario/eliminar/<int:id>')
@login_required
def eliminar_usuario(id):
    if session.get('role') not in ['admin', 'sistemas']: # Control de acceso.
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('usuarios'))

    if id == session.get('user_id'): # Evita que el usuario se elimine a sí mismo.
        flash('No puedes eliminar tu propio usuario activo.', 'warning')
        return redirect(url_for('usuarios'))

    intentos = 3 # Configuración de reintentos.
    for intento in range(intentos):
        try:
            user = User.query.get_or_404(id) # Busca el usuario a borrar.
            db.session.delete(user) # Lo marca para borrado.
            db.session.commit() # Confirma el borrado.
            flash('Usuario eliminado correctamente.', 'success')
            return redirect(url_for('usuarios'))
        except Exception as e:
            db.session.rollback()
            if intento < (intentos - 1):
                time.sleep(1)
            else:
                flash(f'Error al eliminar el usuario: {str(e)}', 'danger')

    return redirect(url_for('usuarios'))

# ==============================================================================
# 7. ARRANQUE DEL SERVIDOR
# ==============================================================================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False) # host='0.0.0.0' permite conexiones externas (HAProxy). debug=False para producción.
