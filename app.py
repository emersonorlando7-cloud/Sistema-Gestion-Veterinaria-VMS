# ==============================================================================
# PROYECTO: VetSystem - Sistema de Gestión Veterinaria
# ARCHIVO: app.py
# DESCRIPCIÓN: Servidor backend en Flask que gestiona el registro de pacientes,
#              dueños y consultas, conectándose a una base de datos MySQL.
# ==============================================================================

# --- IMPORTACIÓN DE LIBRERÍAS ---
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import socket

# --- CONFIGURACIÓN INICIAL DE LA APLICACIÓN ---
app = Flask(__name__)

# Clave secreta necesaria para usar sesiones (como los mensajes "flash" de éxito/error)
app.secret_key = 'clave_secreta_vetsystem_segura' 

# Configuración de la conexión a la base de datos MySQL.
# Formato: mysql+pymysql://usuario:contraseña@IP_del_servidor:puerto/nombre_base_datos
# (Nota: Esta IP apunta a db-01, más adelante la cambiaremos por HAProxy)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.13:3306/vet_clinic_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializamos SQLAlchemy pasándole nuestra aplicación
db = SQLAlchemy(app)

# ==============================================================================
# DEFINICIÓN DE MODELOS (Tablas de la Base de Datos)
# ==============================================================================

class Owner(db.Model):
    """Modelo para la tabla 'owners'. Almacena los datos del dueño de la mascota."""
    __tablename__ = 'owners'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False) # Nombre obligatorio
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(255))

class Pet(db.Model):
    """Modelo para la tabla 'pets'. Almacena los datos de la mascota."""
    __tablename__ = 'pets'
    id = db.Column(db.Integer, primary_key=True)
    # Llave foránea: Conecta la mascota con su dueño
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id')) 
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(50))
    breed = db.Column(db.String(50))
    age = db.Column(db.Integer)
    weight = db.Column(db.Numeric(5, 2))

class Consultation(db.Model):
    """Modelo para la tabla 'consultations'. Almacena el historial médico."""
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    # Llave foránea: Conecta la consulta con la mascota
    pet_id = db.Column(db.Integer, db.ForeignKey('pets.id')) 
    reason = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    # Fecha automática generada por el servidor de base de datos
    consultation_date = db.Column(db.DateTime, server_default=db.func.now())

# ==============================================================================
# RUTAS DE LA APLICACIÓN (Endpoints)
# ==============================================================================

@app.route('/')
def index():
    """Ruta raíz: Si el usuario entra a la página principal, lo redirige al formulario."""
    return redirect(url_for('registrar_paciente'))

@app.route('/registrar', methods=['GET', 'POST'])
def registrar_paciente():
    """
    Ruta principal del sistema. 
    - Si es GET: Muestra el formulario vacío.
    - Si es POST: Procesa los datos del formulario y los guarda en la BD.
    """
    if request.method == 'POST':
        try:
            # 1. Capturar datos del Dueño y guardarlos en la sesión temporal
            owner = Owner(
                name=request.form['owner_name'],
                phone=request.form.get('owner_phone'),
                email=request.form.get('owner_email'),
                address=request.form.get('owner_address')
            )
            db.session.add(owner)
            db.session.flush() # FLUSH: Guarda temporalmente para obtener el ID generado

            # 2. Capturar datos de la Mascota (usando el ID del dueño recién creado)
            pet = Pet(
                owner_id=owner.id,
                name=request.form['pet_name'],
                species=request.form.get('pet_species'),
                breed=request.form.get('pet_breed'),
                age=request.form.get('pet_age'),
                weight=request.form.get('pet_weight')
            )
            db.session.add(pet)
            db.session.flush() # Guarda temporalmente para obtener el ID de la mascota

            # 3. Capturar datos de la Consulta (usando el ID de la mascota)
            consultation = Consultation(
                pet_id=pet.id,
                reason=request.form['reason'],
                diagnosis=request.form.get('diagnosis')
            )
            db.session.add(consultation)
            
            # COMMIT: Confirma y guarda TODOS los cambios permanentemente en la base de datos
            db.session.commit() 
            
            # Mostrar mensaje de éxito
            flash('Paciente registrado exitosamente!', 'success')
            return redirect(url_for('registrar_paciente'))
            
        except Exception as e:
            # Si hay un error, deshacemos todos los cambios para evitar datos corruptos
            db.session.rollback()
            flash(f'Error al registrar: {str(e)}', 'danger')

    # Obtener el nombre del servidor (app-01 o app-02) para mostrarlo en el HTML
    hostname = socket.gethostname()
    
    # Renderizar la plantilla HTML pasando el nombre del host
    return render_template('index.html', hostname=hostname)

# ==============================================================================
# PUNTO DE ENTRADA (Ejecución del servidor)
# ==============================================================================
if __name__ == '__main__':
    # host='0.0.0.0' permite que el servidor acepte conexiones de otras máquinas (como HAProxy o tu PC).
    # debug=True reinicia el servidor automáticamente si haces cambios en el código.
    app.run(host='0.0.0.0', port=5000, debug=True)
