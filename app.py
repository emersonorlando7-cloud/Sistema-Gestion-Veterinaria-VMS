# ==============================================================================
# 1. IMPORTACIÓN DE LIBRERÍAS
# ==============================================================================
# Flask: El framework principal para crear la app web.
# render_template: Permite cargar archivos HTML (Jinja2).
# request: Captura los datos enviados desde formularios (POST/GET).
# redirect / url_for: Redirige al usuario a otras páginas por su nombre de función.
# flash: Muestra mensajes temporales de éxito o error en pantalla.
from flask import Flask, render_template, request, redirect, url_for, flash

# SQLAlchemy: ORM que nos permite manejar la base de datos MySQL usando clases de Python.
from flask_sqlalchemy import SQLAlchemy

# socket: Lo usamos para obtener el nombre del servidor (app-01 o app-02) y mostrarlo.
import socket

# ==============================================================================
# 2. CONFIGURACIÓN INICIAL
# ==============================================================================
app = Flask(__name__)

# Clave secreta obligatoria para que funcionen los mensajes "flash" (cookies seguras).
app.secret_key = 'clave_secreta_vetsystem_segura'

# Cadena de conexión a MySQL (usuario: app_user, pass: AppPass123!, IP: db-01: 192.168.56.13).
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.13:3306/vet_clinic_db'

# Desactiva una advertencia de SQLAlchemy que no es relevante para este proyecto.
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa la base de datos vinculada a nuestra app.
db = SQLAlchemy(app)

# ==============================================================================
# 3. DEFINICIÓN DE MODELOS (Mapeo de las tablas de MySQL a Python)
# ==============================================================================
# Cada clase representa una tabla. Cada db.Column es una columna.

class Owner(db.Model):
    __tablename__ = 'owners' # Nombre exacto de la tabla en MySQL
    id = db.Column(db.Integer, primary_key=True) # Llave primaria autoincremental
    name = db.Column(db.String(100), nullable=False) # Nombre (obligatorio)
    phone = db.Column(db.String(20)) # Teléfono
    email = db.Column(db.String(100)) # Correo
    address = db.Column(db.String(255)) # Dirección

class Pet(db.Model):
    __tablename__ = 'pets'
    id = db.Column(db.Integer, primary_key=True)
    # Llave foránea: enlaza esta mascota con un dueño (owner_id).
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id')) 
    name = db.Column(db.String(100), nullable=False) # Nombre de la mascota (obligatorio)
    species = db.Column(db.String(50)) # Perro, Gato, etc.
    breed = db.Column(db.String(50)) # Raza
    age = db.Column(db.Integer) # Edad
    weight = db.Column(db.Numeric(5, 2)) # Peso con 2 decimales

class Consultation(db.Model):
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    # Llave foránea: enlaza esta consulta con una mascota (pet_id).
    pet_id = db.Column(db.Integer, db.ForeignKey('pets.id')) 
    reason = db.Column(db.Text) # Motivo de la consulta
    diagnosis = db.Column(db.Text) # Diagnóstico
    # Fecha: MySQL la genera automáticamente al momento de insertar.
    consultation_date = db.Column(db.DateTime, server_default=db.func.now())

# ==============================================================================
# 4. RUTAS DE LA APLICACIÓN (Endpoints)
# ==============================================================================

@app.route('/')
def index():
    # Ruta raíz. Si el usuario entra a la IP, lo mandamos al inicio.
    return redirect(url_for('inicio'))

@app.route('/inicio')
def inicio():
    # Cuenta cuántos registros hay en cada tabla para mostrarlos en el Dashboard.
    total_pacientes = Pet.query.count()
    total_duenos = Owner.query.count()
    total_consultas = Consultation.query.count()
    
    # Obtiene el nombre del host (app-01 o app-02).
    hostname = socket.gethostname()
    
    # Carga 'inicio.html' y le pasa las variables para que las dibuje.
    return render_template('inicio.html', hostname=hostname, 
                           total_pacientes=total_pacientes, 
                           total_duenos=total_duenos, 
                           total_consultas=total_consultas)

@app.route('/registrar', methods=['GET', 'POST'])
def registrar_paciente():
    # Si el formulario se envió (POST), procesamos los datos.
    if request.method == 'POST':
        try:
            # 1. Crea un nuevo Dueño en memoria.
            owner = Owner(
                name=request.form['owner_name'], 
                phone=request.form.get('owner_phone'), 
                email=request.form.get('owner_email'), 
                address=request.form.get('owner_address')
            )
            db.session.add(owner) # Lo prepara para guardar.
            db.session.flush()    # Lo guarda temporalmente para obtener su ID generado.

            # 2. Crea la Mascota usando el ID del dueño recién creado.
            pet = Pet(
                owner_id=owner.id, 
                name=request.form['pet_name'], 
                species=request.form.get('pet_species'), 
                breed=request.form.get('pet_breed'), 
                age=request.form.get('pet_age'), 
                weight=request.form.get('pet_weight')
            )
            db.session.add(pet)
            db.session.flush() # Guarda temporalmente para obtener el ID de la mascota.

            # 3. Crea la Consulta usando el ID de la mascota.
            consultation = Consultation(
                pet_id=pet.id, 
                reason=request.form['reason'], 
                diagnosis=request.form.get('diagnosis')
            )
            db.session.add(consultation)
            
            # COMMIT: Confirma todos los cambios en la base de datos (guarda todo).
            db.session.commit() 
            
            # Muestra mensaje de éxito.
            flash('Paciente registrado exitosamente!', 'success')
            # Recarga la misma página para limpiar el formulario.
            return redirect(url_for('registrar_paciente'))
            
        except Exception as e:
            # Si algo falla, deshace los cambios para no dejar datos basura.
            db.session.rollback()
            flash(f'Error al registrar: {str(e)}', 'danger')

    # Si es GET (entrar a la página), solo mostramos el formulario.
    hostname = socket.gethostname()
    return render_template('index.html', hostname=hostname)

@app.route('/pacientes')
def pacientes():
    # Hace un JOIN (unión) entre Mascotas y Dueños para traer los datos juntos.
    lista_pacientes = db.session.query(Pet, Owner).join(Owner, Pet.owner_id == Owner.id).all()
    hostname = socket.gethostname()
    
    # Envía la lista a la plantilla HTML para que la dibuje en la tabla.
    return render_template('pacientes.html', hostname=hostname, pacientes=lista_pacientes)

@app.route('/usuarios')
def usuarios():
    # Página estática de usuarios por ahora.
    hostname = socket.gethostname()
    return render_template('usuarios.html', hostname=hostname)

# ==============================================================================
# 5. PUNTO DE ENTRADA
# ==============================================================================
if __name__ == '__main__':
    # host='0.0.0.0' permite que HAProxy y tu PC (Windows) se conecten.
    # port=5000 es el puerto por donde escuchará.
    # debug=True reinicia el servidor si haces cambios en el código.
    app.run(host='0.0.0.0', port=5000, debug=True)
