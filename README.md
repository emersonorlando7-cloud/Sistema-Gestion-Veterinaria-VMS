# 🐾 Sistema de Gestión Veterinaria (VMS) — Alta Disponibilidad

Aplicación web para la gestión de una clínica veterinaria (pacientes, dueños,
citas médicas, bitácora clínica, usuarios y roles), desplegada sobre una
infraestructura Linux de alta disponibilidad con balanceo de carga y
replicación de base de datos.

---

## 🏗️ Arquitectura

| Host | IP | Rol | Stack |
|------|-----|------|-------|
| `lb-01` | 192.168.56.10 | Balanceador web + MySQL | HAProxy |
| `app-01` | 192.168.56.11 | Servidor de aplicación 1 | Flask + Gunicorn |
| `app-02` | 192.168.56.12 | Servidor de aplicación 2 | Flask + Gunicorn |
| `db-01` | 192.168.56.13 | Base de datos principal | MySQL 8 |
| `db-02` | 192.168.56.14 | Base de datos de respaldo | MySQL 8 |

Flujo de una petición:

    Usuario → lb-01:80 (HAProxy) → app-01 / app-02:5000 (Flask) → lb-01:3306 → db-01 / db-02

Si `app-01` falla, HAProxy redirige el tráfico a `app-02` sin que el usuario lo note.
Si `db-01` falla, HAProxy redirige las consultas a `db-02`.

---

## 🛠️ Stack tecnológico

- **Backend:** Python 3 + Flask 3 + SQLAlchemy + PyMySQL
- **Servidor WSGI:** Gunicorn (3 workers por nodo)
- **Base de datos:** MySQL 8 con replicación maestro-maestro
- **Balanceador:** HAProxy (roundrobin web + failover MySQL)
- **Frontend:** Jinja2 + Bootstrap 5.3.3
- **Firewall:** UFW (reglas por servicio e IP)
- **Acceso remoto:** SSH
- **Exposición pública:** Ngrok
- **Respaldos:** `mysqldump` + `rclone` a Google Drive

---

## 📚 Documentación

Toda la documentación del proyecto vive en la carpeta [`Documentacion/`](Documentacion/):

| Guía | Contenido |
|------|-----------|
| [Guía de la aplicación](Documentacion/Guia_App.txt) | Código Flask (`app.py`) explicado línea por línea: modelos, decoradores, rutas, seguridad |
| [Guía del proyecto](Documentacion/Guia_Proyecto.txt) | Instalación general: red, MySQL, replicación, HAProxy, UFW, Ngrok, rclone |
| [Guía de configuración SSH](Documentacion/Guia_Configuracion_SSH.txt) | Instalación de SSH, firewall y conexión desde Windows |

---

## 🚀 Inicio rápido (desarrollo local)

```bash
# Clonar el repositorio (usando el nombre actualizado).
git clone https://github.com/emersonorlando7-cloud/Sistema-Gestion-Veterinaria-VMS.git
cd Sistema-Gestion-Veterinaria-VMS

# Crear y activar el entorno virtual.
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias.
pip install -r requirements.txt

# Crear el archivo .env a partir de la plantilla.
cp .env.example .env
# Editar .env con los valores reales del entorno.

# Ejecutar la aplicación.
python app.py
