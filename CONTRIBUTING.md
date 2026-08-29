# Contribuir a SquidManager

¡Gracias por tu interés en contribuir! Este documento explica cómo hacerlo.

---

## 🚀 Empezar

### Requisitos de desarrollo
- Docker + Docker Compose
- Git
- Editor de código (VS Code recomendado)

### Configurar entorno de desarrollo

```bash
# Fork el repositorio en GitHub
# Clona tu fork
git clone https://github.com/TU_USUARIO/squid-manager.git
cd squid-manager

# Añade el upstream
git remote add upstream https://github.com/luislopezsanchez/squid-manager.git

# Levanta el entorno
cp .env.example .env
nano .env  # DB_PASS y SECRET_KEY son obligatorios
docker compose up -d
```

### Desarrollo del backend

La imagen de producción arranca **sin** recarga automática: cualquier cambio en `backend/app/` requiere reconstruir o reiniciar el contenedor.

```bash
# Reconstruir tras cambiar código o dependencias
docker compose build backend
docker compose up -d backend

# Ver logs del backend
docker compose logs -f backend

# Instalar nueva dependencia para probarla en caliente
docker exec squidmgr-backend pip install nuevo-paquete
# Luego añadir a backend/requirements.txt y reconstruir la imagen
```

Si prefieres recarga automática mientras desarrollas, crea un `docker-compose.override.yml` propio con `command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` y monta `./backend/app:/app/app`; no lo dejes así en producción, ya que consume CPU vigilando el sistema de archivos y reinicia el proceso ante cualquier escritura, perdiendo el estado en memoria.

### Desarrollo del frontend

El frontend se sirve estáticamente vía Nginx en producción. Para desarrollo con hot-reload:

```bash
cd frontend
npm install
npm run dev
# Vite sirve en http://localhost:5173
```

La API no se publica al host por defecto (ver [docs/architecture.md](docs/architecture.md)); para que el `npm run dev` local pueda llamarla, ajusta el proxy de Vite en `vite.config.ts` o publica el puerto 8000 temporalmente en tu propio override de desarrollo.

Para rebuild del contenedor frontend después de cambios:

```bash
docker compose build frontend
docker compose up -d frontend
```

---

## 📝 Estructura del código

### Backend
- **Models** (`app/models/`): Definiciones de tablas SQLAlchemy (11 modelos, 12 tablas)
- **Schemas** (`app/schemas/`): Validación Pydantic para requests/responses
- **Routes** (`app/routes/`): Endpoints REST de FastAPI (14 routers)
- **Services** (`app/services/`): Lógica de negocio, incluida la validación de configuración y de nombres/valores contra inyección
- **Templates** (`app/templates/`): Template Jinja2 para generar squid.conf
- **Migrations** (`migrations/`): Migraciones de esquema con Alembic — cualquier cambio en un modelo necesita una migración nueva (`alembic revision --autogenerate -m "..."`, revisada a mano)

### Frontend
- **Pages** (`src/pages/`): Una página por sección del panel (16 páginas)
- **Components** (`src/components/`): Layout, Icons (juego de iconos de línea propio), AuthShell, Toast
- **API** (`src/api/client.ts`): Cliente HTTP con todos los endpoints

---

## 🔄 Flujo de trabajo

1. Crea un branch: `git checkout -b feature/mi-feature`
2. Haz tus cambios
3. Testea: `docker compose up -d` y prueba manualmente
4. Commit: `git commit -m "feat: descripción del cambio"`
5. Push: `git push origin feature/mi-feature`
6. Abre un Pull Request en GitHub

### Convención de commits

Usamos [Conventional Commits](https://www.conventionalcommits.org/):

| Tipo | Descripción |
|------|-------------|
| `feat:` | Nueva funcionalidad |
| `fix:` | Corrección de bug |
| `docs:` | Cambios en documentación |
| `refactor:` | Refactorización de código |
| `style:` | Cambios de formato/estilo |
| `test:` | Añadir o modificar tests |
| `chore:` | Tareas de mantenimiento |

Ejemplo: `feat: añadir página de logs en tiempo real`

---

## 🧪 Testing

### Tests del backend
```bash
docker exec squidmgr-backend pytest
```

### Tests manuales
Verificar que las funcionalidades principales siguen funcionando:
1. Login del panel y cambio de contraseña
2. Crear/editar/eliminar usuarios y grupos
3. Crear/editar/eliminar ACLs y reglas
4. Aplicar cambios (comprobar que la validación rechaza una configuración rota antes de escribirla)
5. Navegar a través del proxy, con y sin SSL Bump

---

## 📋 Checklist antes de un Pull Request

- [ ] El código funciona localmente
- [ ] Los contenedores levantan sin errores
- [ ] Si cambiaste un modelo, generaste y revisaste la migración de Alembic correspondiente
- [ ] No se incluyen credenciales ni secrets
- [ ] Se actualizó la documentación si es necesario
- [ ] Se actualizó el CHANGELOG.md
- [ ] Los commits siguen la convención

---

## 🐛 Reportar bugs

Si encuentras un bug, abre un [Issue](https://github.com/luislopezsanchez/squid-manager/issues) con:

1. **Descripción** del problema
2. **Pasos para reproducirlo**
3. **Comportamiento esperado** vs **comportamiento actual**
4. **Logs** (`docker compose logs`)
5. **Versión** de SquidManager

---

## 💡 Sugerir funcionalidades

Abre un [Issue](https://github.com/luislopezsanchez/squid-manager/issues) con la etiqueta `enhancement` describiendo:
- Qué funcionalidad te gustaría
- Por qué sería útil
- Cómo te imaginas que funcionaría

---

## 📄 Licencia

Al contribuir, aceptas que tus cambios se publiquen bajo la licencia Apache-2.0.

---

## Documentación traducida

El README y las dos guías de instalación existen también en inglés
(`.en.md`) y portugués (`.pt.md`). El resto de la documentación está solo en
español, a propósito: mantener 25.000 palabras por triplicado cuesta más de lo
que aporta, y una traducción desactualizada es peor que no tenerla.

**El español es la fuente de verdad.** Si cambias uno de esos cinco documentos:

1. Cambia primero la versión en español.
2. Lleva el cambio a `.en.md` y `.pt.md` en el mismo commit.

Si no puedes traducirlo en ese momento, dilo en el commit para que se vea que
las copias han quedado atrás. Cada fichero traducido lleva arriba una nota que
avisa al lector de que el español manda si discrepan, precisamente para que un
desfase sea molesto pero no peligroso.

Los idiomas del producto —el panel y los mensajes de la API— son otra cosa y
están en [docs/idiomas.md](docs/idiomas.md).
