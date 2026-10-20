# ==============================================================================
# PROYECTO: VetSystem - Sistema de Gestión Veterinaria
# ARCHIVO: app.py (Backend principal)
# DESCRIPCIÓN: Servidor Flask conectado a MySQL.
# ==============================================================================

# --- IMPORTACIÓN DE LIBRERÍAS ---
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import socket

# --- CONFIGURACIÓN INICIAL ---
app = Flask(__name__)

# Clave para que funcionen los mensajes de alerta (flash)
app.secret_key = 'clave_secreta_vetsystem_segura'

# Cadena de conexión a MySQL (db-01)
# Formato: mysql+pymysql://usuario:password@IP:puerto/nombre_db
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://app_user:AppPass123!@192.168.56.13:3306/vet_clinic_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializamos SQLAlchemy
db = SQLAlchemy(app)

# ==============================================================================
# MODELOS (Mapeo de las tablas de MySQL a clases de Python)
# ==============================================================================

class Owner(db.Model):
    # Representa la tabla 'owners' (Dueños)
    __tablename__ = 'owners'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False) # Campo obligatorio
    phone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    address = db.Column(db.String(255))

class Pet(db.Model):
    # Representa la tabla 'pets' (Mascotas)
    __tablename__ = 'pets'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('owners.id')) # Relación con Dueño
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(50))
    breed = db.Column(db.String(50))
    age = db.Column(db.Integer)
    weight = db.Column(db.Numeric(5, 2))

class Consultation(db.Model):
    # Representa la tabla 'consultations' (Consultas médicas)
    __tablename__ = 'consultations'
    id = db.Column(db.Integer, primary_key=True)
    pet_id = db.Column(db.Integer, db.ForeignKey('pets.id')) # Relación con Mascota
    reason = db.Column(db.Text)
    diagnosis = db.Column(db.Text)
    consultation_date = db.Column(db.DateTime, server_default=db.func.now()) # Fecha automática

# ==============================================================================
# RUTAS DE LA APLICACIÓN (Controladores)
# ==============================================================================

@app.route('/')
def index():
    # Si entran a la raíz, redirigir al inicio
    return redirect(url_for('inicio'))

@app.route('/inicio')
def inicio():
    # Cuenta los registros en la base de datos para mostrarlos en el Dashboard
    total_pacientes = Pet.query.count()
    total_duenos = Owner.query.count()
    total_consultas = Consultation.query.count()
    
    # Obtiene el nombre de la máquina (app-01 o app-02)
    hostname = socket.gethostname()
    
    # Renderiza el HTML pasando las variables
    return render_template('inicio.html', hostname=hostname, 
                           total_pacientes=total_pacientes, 
                           total_duenos=total_duenos, 
                           total_consultas=total_consultas)

@app.route('/registrar', methods=['GET', 'POST'])
def registrar_paciente():
    if request.method == 'POST':
        try:
            # 1. Guardar Dueño
            owner = Owner(
                name=request.form['owner_name'], 
                phone=request.form.get('owner_phone'), 
                email=request.form.get('owner_email'), 
                address=request.form.get('owner_address')
            )
            db.session.add(owner)
            db.session.flush() # Obtiene el ID del dueño sin guardar permanentemente aún

            # 2. Guardar Mascota (usando el ID del dueño)
            pet = Pet(
                owner_id=owner.id, 
                name=request.form['pet_name'], 
                species=request.form.get('pet_species'), 
                breed=request.form.get('pet_breed'), 
                age=request.form.get('pet_age'), 
                weight=request.form.get('pet_weight')
            )
            db.session.add(pet)
            db.session.flush() # Obtiene el ID de la mascota

            # 3. Guardar Consulta (usando el ID de la mascota)
            consultation = Consultation(
                pet_id=pet.id, 
                reason=request.form['reason'], 
                diagnosis=request.form.get('diagnosis')
            )
            db.session.add(consultation)
            
            db.session.commit() # Guarda TODO en la base de datos definitivamente
            
            flash('Paciente registrado exitosamente!', 'success')
            return redirect(url_for('registrar_paciente'))
            
        except Exception as e:
            db.session.rollback() # Si hay error, cancela todo para no dejar datos basura
            flash(f'Error al registrar: {str(e)}', 'danger')

    hostname = socket.gethostname()
    return render_template('index.html', hostname=hostname)

@app.route('/pacientes')
def pacientes():
    # Consulta SQL (JOIN) para traer Mascotas con sus Dueños
    lista_pacientes = db.session.query(Pet, Owner).join(Owner, Pet.owner_id == Owner.id).all()
    hostname = socket.gethostname()
    return render_template('pacientes.html', hostname=hostname, pacientes=lista_pacientes)

@app.route('/usuarios')
def usuarios():
    hostname = socket.gethostname()
    return render_template('usuarios.html', hostname=hostname)

# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================
if __name__ == '__main__':
    # 0.0.0.0 permite conexiones externas (para HAProxy y tu PC)
    app.run(host='0.0.0.0', port=5000, debug=True)
